import os
from dotenv import load_dotenv
from src.paths import ENV_FILE


def main():
    from src.single_instance import acquire_instance, release_instance
    handle, acquired = acquire_instance()
    if not acquired:
        return
    # Existing shell variables take precedence over the local environment file.
    load_dotenv(ENV_FILE, override=False)
    try:
        from src.app import PetApp
        api_key = os.environ.get("SETTA_API_KEY", "")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        app = PetApp(api_key, gemini_key)
        app.run()
    finally:
        release_instance(handle)


if __name__ == "__main__":
    main()
