# Generation I (OakVar) as it stood for the May 2023 benchmark run, rebuilt for the A3 re-run.
#
# OakVar 2.9.15 is the release current on 2023-05-07 (published 2023-05-06). Its Python
# dependencies are resolved as of that date with uv's --exclude-newer, so a rebuild today gets the
# same versions instead of whatever is newest. The image holds no module and no credential: the
# OakVar home (store login, annotator data, installed modules) is a volume mounted at /oakvar.
#
#   docker build -t jdl-bench-oakvar:2.9.15 docs/manuscript/benchmarks/a3/oakvar
FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370

COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /usr/local/bin/uv

ARG OAKVAR_VERSION=2.9.15
ARG EXCLUDE_NEWER=2023-05-08T00:00:00Z

# mako is longevity2reporter's only pypi_dependency; installing it here keeps OakVar from
# pip-installing it at module-install time.
RUN uv pip install --system --no-cache --exclude-newer "${EXCLUDE_NEWER}" \
        "oakvar==${OAKVAR_VERSION}" mako \
    && uv pip freeze --system > /pip-freeze.txt

# Run as the host user (uid/gid passed at `docker run --user`); HOME is the mounted OakVar home.
ENV HOME=/oakvar \
    OV_ROOT_DIR=/oakvar/ov
WORKDIR /work
ENTRYPOINT ["ov"]
