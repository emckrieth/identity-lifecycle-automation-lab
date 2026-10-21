"""Start a local-only Snipe-IT sandbox and retain credentials in an ignored file."""
import argparse
import base64
import json
import secrets
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / "sandbox/assets/.env"


def load_env():
    return dict(line.split("=", 1) for line in ENV.read_text().splitlines() if "=" in line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", required=True)
    args = parser.parse_args()
    ENV.parent.mkdir(parents=True, exist_ok=True)
    if not ENV.exists():
        values = {
            "APP_ENV": "production", "APP_DEBUG": "false",
            "APP_KEY": "base64:" + base64.b64encode(secrets.token_bytes(32)).decode(),
            "APP_URL": "http://127.0.0.1:8090", "APP_TIMEZONE": "UTC",
            "APP_LOCALE": "en-US", "DB_CONNECTION": "mariadb", "DB_HOST": "db",
            "DB_PORT": "3306", "DB_DATABASE": "snipeit", "DB_USERNAME": "snipeit",
            "DB_PASSWORD": secrets.token_urlsafe(32),
            "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(32),
            "LAB_ASSET_ADMIN_PASSWORD": secrets.token_urlsafe(32),
            "MAIL_MAILER": "log", "MAIL_FROM_ADDR": "lab@example.invalid",
            "MAIL_FROM_NAME": "Portfolio", "PRIVATE_FILESYSTEM_DISK": "local",
            "PUBLIC_FILESYSTEM_DISK": "local_public", "IMAGE_LIB": "gd",
            "SESSION_DRIVER": "file", "QUEUE_CONNECTION": "sync",
            "CACHE_DRIVER": "file", "BACKUP_ENV": "false", "APP_FORCE_TLS": "false"}
        ENV.write_text("".join(k + "=" + v + "\n" for k, v in values.items()))
    values = load_env()
    compose = [args.docker, "compose", "--project-name", "portfolio-assets-lab",
               "--env-file", str(ENV), "-f", str(ROOT / "sandbox/assets/compose.yaml")]

    def call(*command, allow_failure=False):
        result = subprocess.run(compose + list(command), capture_output=True,
                                text=True, cwd=ROOT, timeout=300)
        if result.returncode and not allow_failure:
            raise RuntimeError("Snipe-IT Docker operation failed: " + command[0])
        return result

    print("Starting isolated Snipe-IT (first image download may take a few minutes)...", flush=True)
    call("up", "-d")
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 120
    while True:
        try:
            with opener.open("http://127.0.0.1:8090/login", timeout=3) as response:
                if response.status == 200:
                    break
        except (URLError, OSError):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("Snipe-IT did not become ready within 120 seconds")
        time.sleep(2)
    settings = ('$s=\\App\\Models\\Setting::first(); if (!$s) { '
                '$s=new \\App\\Models\\Setting(); $s->site_name="Portfolio Asset Lab"; '
                '$s->brand=1; $s->save(); }')
    call("exec", "-T", "app", "php", "artisan", "tinker", "--execute=" + settings)
    if not values.get("SNIPEIT_TOKEN"):
        # Supported artisan commands bootstrap this empty, private lab only.
        call("exec", "-T", "app", "php", "artisan", "snipeit:create-admin",
             "--first_name=Portfolio", "--last_name=Admin", "--email=lab-admin@example.invalid",
             "--username=lab-admin", "--password=" + values["LAB_ASSET_ADMIN_PASSWORD"],
             allow_failure=True)
        call("exec", "-T", "app", "php", "artisan", "passport:keys", "--no-interaction", allow_failure=True)
        call("exec", "-T", "app", "chown", "docker:root",
             "/var/lib/snipeit/keys/oauth-private.key", "/var/lib/snipeit/keys/oauth-public.key")
        call("exec", "-T", "app", "php", "artisan", "passport:client",
             "--personal", "--name=Portfolio Lab", "--no-interaction")
        result = call("exec", "-T", "app", "php", "artisan", "snipeit:make-api-key",
                      "--user_id=1", "--name=portfolio-lab", "--key-only")
        tokens = [line.strip() for line in result.stdout.splitlines()
                  if line.strip().startswith("eyJ") and line.strip().count(".") == 2]
        if len(tokens) != 1:
            raise RuntimeError("Expected one API token; inspect local bootstrap configuration")
        with ENV.open("a") as handle:
            handle.write("SNIPEIT_TOKEN=" + tokens[0] + "\n")
    print(json.dumps({"status": "ready", "endpoint": "http://127.0.0.1:8090",
                      "credentials": "retained only in ignored sandbox/assets/.env"}))


if __name__ == "__main__":
    main()
