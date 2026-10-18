FROM ubuntu:22.04 AS package

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY pyproject.toml setup.py _build_backend.py MANIFEST.in README.md LICENSE ./
COPY modules/ modules/
COPY mypyconsole/ mypyconsole/
COPY mypylib/ mypylib/
COPY mytoncore/ mytoncore/
COPY mytonctrl/ mytonctrl/
COPY mytoninstaller/ mytoninstaller/
ARG MYTONCTRL_COMMIT=unknown
ARG MYTONCTRL_VERSION=unknown
ARG MYTONCTRL_IMAGE_REF=
RUN python3 -c 'import os; from pathlib import Path; Path("mytonctrl/_version.py").write_text("__commit__ = " + repr(os.environ["MYTONCTRL_COMMIT"]) + "\n__version__ = " + repr(os.environ["MYTONCTRL_VERSION"]) + "\n__image_ref__ = " + repr(os.environ["MYTONCTRL_IMAGE_REF"]) + "\n")' \
    && python3 -m pip wheel --no-deps --wheel-dir /wheels .

FROM ubuntu:22.04 AS benchmark

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PYTHON_INSTALL_DIR=/opt/mytonctrl/benchmark/python \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && uv python install 3.14 \
    && uv venv --python 3.14 /opt/mytonctrl/benchmark/venv
ARG TON_BENCHMARK_REVISION=3d478cbde854be03a18ab2a59f8fc3c565cf7d14
COPY docker/prepare-benchmark.py /build/prepare-benchmark.py
RUN /opt/mytonctrl/benchmark/venv/bin/python /build/prepare-benchmark.py \
        /opt/mytonctrl/benchmark/source --revision "${TON_BENCHMARK_REVISION}" \
    && uv pip install --python /opt/mytonctrl/benchmark/venv/bin/python --only-binary :all: \
        --editable /opt/mytonctrl/benchmark/source/test/tontester \
    && /opt/mytonctrl/benchmark/venv/bin/python /opt/mytonctrl/benchmark/source/test/tontester/generate_tl.py \
    && /opt/mytonctrl/benchmark/venv/bin/python -c 'from contract import WalletV1; from tontester.network import Network; from tontester.zerostate import SimplexConsensusConfig' \
    && chmod -R a+rX /opt/mytonctrl/benchmark

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MYTONCTRL_CONTAINER=1 \
    PATH=/opt/mytonctrl/bin:/opt/mytonctrl/venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv supervisor sudo ca-certificates curl wget git \
        libatomic1 libstdc++6 libgcc-s1 libssl3 libsodium23 liblz4-1 \
        libjemalloc2 libmicrohttpd12 \
        fio iproute2 plzip pv aria2 rocksdb-tools sysstat iotop \
        iputils-ping nload jq bc xxd htop procps \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/mytonctrl/venv \
    && touch /etc/mytonctrl-container \
    && useradd --create-home --shell /bin/bash validator
COPY --from=package /wheels /wheels
COPY --from=benchmark /opt/mytonctrl/benchmark /opt/mytonctrl/benchmark
COPY --from=benchmark /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/
RUN /opt/mytonctrl/venv/bin/pip install --only-binary=:all: /wheels/*.whl \
    && rm -rf /wheels
COPY docker/entrypoint.py docker/console.py docker/run-service.py docker/mytonctrl_docker_args.py docker/benchmark.py /usr/local/lib/mytonctrl/
COPY docker/export-ton.sh /usr/local/lib/mytonctrl/export-ton.sh
COPY docker/systemctl.py /usr/local/bin/systemctl
COPY docker/supervisord.conf /etc/supervisor/mytonctrl.conf
COPY docker/bash-aliases.sh /etc/mytonctrl-aliases.sh
RUN chmod 755 /usr/local/bin/systemctl \
    && mkdir -p /opt/mytonctrl/bin \
    && ln -s /usr/local/lib/mytonctrl/console.py /opt/mytonctrl/bin/mytonctrl \
    && chmod 755 /usr/local/lib/mytonctrl/console.py \
    && chmod 644 /etc/mytonctrl-aliases.sh \
    && printf '\n. /etc/mytonctrl-aliases.sh\n' >> /etc/bash.bashrc
WORKDIR /var/ton-work
STOPSIGNAL SIGTERM
ENTRYPOINT ["/opt/mytonctrl/venv/bin/python", "/usr/local/lib/mytonctrl/entrypoint.py"]
CMD ["run"]
