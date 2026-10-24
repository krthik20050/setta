"""Private, explicit device-location answers with an offline city-name lookup."""
import re


def asks_for_device_location(text):
    """Match direct requests for the user's current position, not general location talk."""
    value = re.sub(r'\s+', ' ', str(text or '').strip().casefold())
    value = re.sub(r'[.!?]+$', '', value).strip()
    return bool(
        re.search(r'\bwhere\s+am\s+i(?:\s+(?:right\s+now|currently))?\b', value) or
        re.search(r"\bwhat(?:'s| is)\s+my\s+(?:(?:exact|precise|approximate|current|present)\s+)?location\b", value) or
        re.search(r'\bfind\s+my\s+location\b|\bshow\s+my\s+location\b', value) or
        re.search(r'मैं\s+कहाँ\s+हूँ|मेरी\s+(?:अभी\s+की\s+)?लोकेशन\s+कहाँ\s+है', value) or
        re.search(r'ഞാൻ\s+എവിടെയാണ്|എന്റെ\s+(?:ഇപ്പോഴത്തെ\s+)?ലൊക്കേഷൻ\s+എവിടെയാണ്', value) or
        re.search(r'\bnjan\s+evide(?:ya| aanu)\b|\bente\s+location\s+evideya\b', value)
    )


def answer_current_location(provider, profile, language='en-IN'):
    """Resolve one fresh position locally; never persist or send coordinates to a provider."""
    if not profile.allowed('location'):
        return _localized(language,
            'Turn on “Use location when asked” in Profile & Memory first.',
            'पहले Profile & Memory में “Use location when asked” चालू करें।',
            'ആദ്യം Profile & Memory-ൽ “Use location when asked” ഓൺ ചെയ്യൂ.')
    if provider is None:
        return _localized(language,
            'Windows location support is not available in this Setta build.',
            'इस Setta build में Windows location support उपलब्ध नहीं है।',
            'ഈ Setta പതിപ്പിൽ Windows location support ലഭ്യമല്ല.')

    try:
        result = provider.get_current_location()
    except Exception:
        result = {'status': 'unavailable'}
    status = result.get('status') if isinstance(result, dict) else None
    if status == 'denied':
        return _localized(language,
            'Windows did not allow location access. Turn on Location services in Windows Settings, then try again.',
            'Windows ने location access नहीं दिया। Windows Settings में Location services चालू करके फिर कोशिश करें।',
            'Windows location access അനുവദിച്ചില്ല. Windows Settings-ൽ Location services ഓൺ ചെയ്ത് വീണ്ടും ശ്രമിക്കൂ.')
    if status == 'timeout':
        return _localized(language,
            'Windows could not get a location fix in time. Check that Location services are on and try again.',
            'Windows समय पर location नहीं पा सका। Location services चालू हैं या नहीं देखें और फिर कोशिश करें।',
            'Windows-ന് സമയത്ത് location ലഭിച്ചില്ല. Location services ഓൺ ആണെന്ന് പരിശോധിച്ച് വീണ്ടും ശ്രമിക്കൂ.')
    if status != 'ok':
        return _localized(language,
            'I could not get a location from Windows. Check Location services and try again.',
            'Windows से location नहीं मिल सकी। Location services जाँचकर फिर कोशिश करें।',
            'Windows-ൽ നിന്ന് location ലഭിച്ചില്ല. Location services പരിശോധിച്ച് വീണ്ടും ശ്രമിക്കൂ.')

    latitude, longitude = result['latitude'], result['longitude']
    try:
        import reverse_geocode
        place = reverse_geocode.get((latitude, longitude))
        locality = str(place.get('city', '')).strip()
        parts = [locality, str(place.get('state', '')).strip(), str(place.get('country', '')).strip()]
        place_name = ', '.join(dict.fromkeys(part for part in parts if part))
    except (ImportError, OSError, ValueError, TypeError, KeyError):
        place_name = ''

    if place_name:
        return _localized(language,
            f'You appear to be near {place_name}. This is an approximate city-level match from offline GeoNames data, not a street address.',
            f'आप लगभग {place_name} के पास हैं। यह offline GeoNames data से मिला अनुमानित शहर-स्तर का स्थान है, street address नहीं।',
            f'നിങ്ങൾ ഏകദേശം {place_name}-ന് സമീപമാണെന്ന് തോന്നുന്നു. ഇത് offline GeoNames data ഉപയോഗിച്ചുള്ള ഏകദേശ നഗരതല സ്ഥാനമാണ്; street address അല്ല.')

    latitude_label = f'{abs(latitude):.4f}° {"N" if latitude >= 0 else "S"}'
    longitude_label = f'{abs(longitude):.4f}° {"E" if longitude >= 0 else "W"}'
    return _localized(language,
        f'Your approximate coordinates are {latitude_label}, {longitude_label}. I could not match them to a nearby city offline.',
        f'आपके अनुमानित coordinates {latitude_label}, {longitude_label} हैं। Offline lookup से पास का शहर नहीं मिला।',
        f'നിങ്ങളുടെ ഏകദേശ coordinates {latitude_label}, {longitude_label} ആണ്. Offline lookup-ൽ അടുത്ത നഗരം കണ്ടെത്താനായില്ല.')


def _localized(language, english, hindi, malayalam):
    if language == 'hi-IN':
        return hindi
    if language == 'ml-IN':
        return malayalam
    return english
