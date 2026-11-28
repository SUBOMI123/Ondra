"""Build and push an image to Fly's registry from a machine whose outbound HTTPS goes through an intercepting proxy
(Ondra's cloud build sessions). Anywhere else, plain `fly deploy` builds fine and you don't need this.

    python infra/deploy/sandbox_build.py --app ondra-api-staging --dockerfile apps/api/Dockerfile
    fly deploy . -c infra/fly/api.toml --image registry.fly.io/ondra-api-staging:<tag printed above>

Builds inside `docker build` can't reach the proxy on 127.0.0.1 and don't trust its certificate (/root/.ccr/README.md).
So: --network host, the proxy settings as build args (Docker's predefined proxy args, not kept in the image), and a
variant of the Dockerfile in which each RUN step sees the proxy's CA bundle through a BuildKit secret mount. The
certificate exists only while that step runs: nothing about the proxy ends up in the image, and the real Dockerfile
is unchanged. Official base images (python, node) come through mirror.gcr.io, since the sandbox often hits Docker Hub's
anonymous rate limit.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

CA = os.getenv("SANDBOX_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
TRUST = ("--mount=type=secret,id=ca,target=/tmp/ca.crt "
         "SSL_CERT_FILE=/tmp/ca.crt PIP_CERT=/tmp/ca.crt REQUESTS_CA_BUNDLE=/tmp/ca.crt CURL_CA_BUNDLE=/tmp/ca.crt "
         "NODE_EXTRA_CA_CERTS=/tmp/ca.crt UV_NATIVE_TLS=1 HF_HUB_DISABLE_XET=1 ")


def variant(dockerfile: str) -> str:
    """Every `RUN cmd` becomes `RUN --mount=<ca> VAR=... cmd` (shell form only, which is all our Dockerfiles use)."""
    with open(dockerfile) as f:
        text = f.read()
    text = re.sub(r"^RUN (?!\[)", "RUN " + TRUST, text, flags=re.MULTILINE)
    # Official Docker Hub images through Google's mirror: the sandbox shares its address with others, so Docker Hub's
    # anonymous rate limit (429) is often used up. Same images, same tags.
    return re.sub(r"^FROM (?!\S+/)(\S+)", r"FROM mirror.gcr.io/library/\1", text, flags=re.MULTILINE)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--app", required=True)
    p.add_argument("--dockerfile", required=True)
    p.add_argument("--context", default=".")
    p.add_argument("--build-arg", action="append", default=[])
    a = p.parse_args()
    tag = f"registry.fly.io/{a.app}:sandbox-{int(time.time())}"
    proxy = {k: v for k in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy")
             if (v := os.environ.get(k))}
    with tempfile.NamedTemporaryFile("w", suffix=".Dockerfile", delete=False) as f:
        f.write(variant(a.dockerfile))
    cmd = ["docker", "build", "--network", "host", "--secret", f"id=ca,src={CA}", "-f", f.name, "-t", tag]
    for k, v in proxy.items():
        cmd += ["--build-arg", f"{k}={v}"]
    for b in a.build_arg:
        cmd += ["--build-arg", b]
    cmd.append(a.context)
    env = {**os.environ, "DOCKER_BUILDKIT": "1"}
    if subprocess.run(cmd, env=env, check=False).returncode:
        sys.exit("build failed")
    if subprocess.run(["fly", "auth", "docker"], check=False, capture_output=True).returncode:
        sys.exit("fly auth docker failed (signed in to Fly?)")
    if subprocess.run(["docker", "push", tag], check=False).returncode:
        sys.exit("push failed")
    print(f"\nIMAGE {tag}")


if __name__ == "__main__":
    main()
