# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.209.6/containers/debian/.devcontainer/base.Dockerfile

# [Choice] Debian version (use bullseye or stretch on local arm64/Apple Silicon): bullseye, buster, stretch
ARG VARIANT="buster"
FROM mcr.microsoft.com/vscode/devcontainers/base:0-${VARIANT}

# ** [Optional] Uncomment this section to install additional packages. **
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>

# Install DDEV.
RUN curl -fsSL https://apt.fury.io/drud/gpg.key | sudo apt-key add - \
    && echo "deb https://apt.fury.io/drud/ * *"  >> /etc/apt/sources.list.d/ddev.list \
    && apt-get update \
    && apt-get install -y ddev

ENV NVM_DIR $HOME/.nvm
ENV NODE_VERSION v16.13.1

RUN mkdir -p $NVM_DIR
RUN apt-get update && echo "y" | apt-get install curl
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
RUN /bin/bash -c "source $NVM_DIR/nvm.sh && nvm install $NODE_VERSION && nvm use --delete-prefix $NODE_VERSION"
ENV NODE_PATH $NVM_DIR/versions/node/$NODE_VERSION/bin
ENV PATH $NODE_PATH:$PATH

RUN apt-get -y install build-essential autoconf libtool bison re2c pkg-config libxml2-dev libsqlite3-dev openssl

RUN git clone https://github.com/php/php-src.git --branch=PHP-8.3.10 --single-branch \
    && cd php-src \
    && ./buildconf \
    &&  ./configure --with-openssl \
    && make install

RUN curl -sS https://platform.sh/cli/installer | php
ENV PLATFORM_PATH $HOME/.platformsh/bin
ENV PATH $PLATFORM_PATH:$PATH
