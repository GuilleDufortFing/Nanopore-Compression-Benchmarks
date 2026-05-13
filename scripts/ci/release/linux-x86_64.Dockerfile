FROM fedora:36 AS base

WORKDIR /builder

# Configure dnf stage
RUN echo "max_parallel_downloads=20" >> /etc/dnf/dnf.conf

RUN dnf install -y \
    wget \
    git \
    pax-utils && \
    dnf clean all

COPY scripts/ci/release/linux-x86_64.conda-env.yaml .

RUN mkdir -p ~/miniconda3
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
RUN bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
RUN rm -rf ~/miniconda3/miniconda.sh
RUN ~/miniconda3/bin/conda init bash && \
    source ~/.bashrc && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    conda env create --file=linux-x86_64.conda-env.yaml && \
    conda clean -afy

FROM base AS build

COPY . .

ENTRYPOINT /builder/scripts/ci/release/make-release-worker.sh