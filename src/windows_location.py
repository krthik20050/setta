"""One-shot Windows location reads, coordinated with Tk's foreground UI thread."""
import asyncio
import math
import threading
import tkinter as tk


class WindowsLocationService:
    """Request a fresh position only when called; never watches location in background."""

    def __init__(self, root):
        self.root = root
        self._loop = asyncio.new_event_loop()
        self._active = None
        self._closed = False

    def get_current_location(self, timeout=70):
        """Block a worker thread while Tk pumps the WinRT async request on its UI thread."""
        if self._closed:
            return {'status': 'unavailable', 'reason': 'Location service is closed.'}
        completed = threading.Event()
        result = {}
        try:
            self.root.after(0, lambda: self._start_request(completed, result))
        except (RuntimeError, AttributeError, tk.TclError):
            return {'status': 'unavailable', 'reason': 'The Setta window is not available.'}
        if not completed.wait(timeout):
            return {'status': 'timeout', 'reason': 'Windows did not return a location in time.'}
        return result.get('value', {'status': 'unavailable', 'reason': 'Location lookup did not finish.'})

    def _start_request(self, completed, result):
        if self._closed:
            result['value'] = {'status': 'unavailable', 'reason': 'Location service is closed.'}
            completed.set()
            return
        if self._active is not None:
            result['value'] = {'status': 'busy', 'reason': 'A location lookup is already running.'}
            completed.set()
            return
        self._active = (completed, result, None)
        try:
            asyncio.set_event_loop(self._loop)
            task = self._loop.create_task(self._read_position())
            self._active = (completed, result, task)
            self._pump_loop()
        except Exception as error:
            self._finish({'status': 'unavailable', 'reason': str(error)})

    async def _read_position(self):
        try:
            import winrt.windows.devices.geolocation as geolocation
        except ImportError:
            return {'status': 'unavailable', 'reason': 'Windows location support is not installed.'}

        try:
            access = await geolocation.Geolocator.request_access_async()
            if access != geolocation.GeolocationAccessStatus.ALLOWED:
                return {'status': 'denied', 'reason': 'Windows location access is not allowed.'}

            locator = geolocation.Geolocator()
            locator.desired_accuracy_in_meters = 100
            position = await asyncio.wait_for(locator.get_geoposition_async(), timeout=35)
            coordinate = position.coordinate
            latitude = float(coordinate.latitude)
            longitude = float(coordinate.longitude)
            accuracy = float(coordinate.accuracy)
            if (not math.isfinite(latitude) or not math.isfinite(longitude) or
                    not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
                return {'status': 'unavailable', 'reason': 'Windows returned invalid coordinates.'}
            return {'status': 'ok', 'latitude': latitude, 'longitude': longitude,
                    'accuracy_meters': accuracy if math.isfinite(accuracy) else None}
        except asyncio.TimeoutError:
            return {'status': 'timeout', 'reason': 'Windows could not determine a location in time.'}
        except Exception:
            return {'status': 'unavailable', 'reason': 'Windows could not determine a location.'}

    def _pump_loop(self):
        if self._closed or self._active is None:
            return
        completed, result, task = self._active
        try:
            self._loop.call_soon(self._loop.stop)
            self._loop.run_forever()
            if task.done():
                try:
                    self._finish(task.result())
                except Exception:
                    self._finish({'status': 'unavailable', 'reason': 'Windows location lookup failed.'})
            else:
                self.root.after(15, self._pump_loop)
        except Exception:
            self._finish({'status': 'unavailable', 'reason': 'Windows location lookup failed.'})

    def _finish(self, value):
        if self._active is None:
            return
        completed, result, _task = self._active
        result['value'] = value
        self._active = None
        completed.set()

    def close(self):
        self._closed = True
        if self._active is not None:
            completed, result, task = self._active
            if task is not None and not task.done():
                task.cancel()
                try:
                    self._loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
                except Exception:
                    pass
            result['value'] = {'status': 'cancelled', 'reason': 'Setta closed during location lookup.'}
            self._active = None
            completed.set()
        if not self._loop.is_closed():
            self._loop.close()
