# Generation I (OakVar) for the A3 re-run. One Dockerfile, two builds:
#
# - current (the one used first, per the user): OakVar 2.13.1, published 2026-08-30 and still the
#   latest on 2026-10-11, with dependencies resolved as of 2026-08-31. Resolving as of the build day
#   pulled polars 2.0.0 (2026-10-06), a major release OakVar was never tested against.
#     docker build -t jdl-bench-oakvar:2.13.1 --build-arg OAKVAR_VERSION=2.13.1 \
#         --build-arg EXCLUDE_NEWER=2026-08-31T00:00:00Z docs/manuscript/benchmarks/a3/oakvar
# - May 2023 (fallback only if the just_* modules fail on the current release): OakVar 2.9.15,
#   published 2023-05-06, dependencies resolved as of 2023-05-08 (the defaults below).
#     docker build -t jdl-bench-oakvar:2.9.15 docs/manuscript/benchmarks/a3/oakvar
#
# uv's --exclude-newer makes a rebuild get the same dependency versions instead of whatever is
# newest. The image holds no module and no credential: the OakVar home (store login, annotator data,
# installed modules) is a volume mounted at /oakvar.
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
