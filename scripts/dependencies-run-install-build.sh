#!/usr/bin/env bash

printf "Installing NPM dependencies for Colby dependencies \n"

shopt -s extglob # Turns on extended globbing

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"  # This loads nvm

<<<<<<< HEAD
# root
printf "Build root... \n"
npm install

printf "Build Colby Theme... \n"
cd web/wp-content/themes/colby-college-theme
composer install
composer dump-autoload
yarn
yarn scripts:build
cd -
=======
printf "Build Colby Theme... \n"
cd web/wp-content/themes/colby-college-theme
composer install
composer dump-autoload
yarn
yarn scripts:build
cd -

>>>>>>> 82e0edde410a5c06b5004614c5c3d74729cc8d35

# npm install
shopt -u extglob