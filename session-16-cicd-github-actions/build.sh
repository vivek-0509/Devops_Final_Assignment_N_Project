#!/bin/bash
# Build step: package the application into build/ with build metadata (uploaded as a CI artifact)
set -e
echo "================================="
echo "Starting Application Build"
echo "================================="
rm -rf build
mkdir -p build
cp -R app build/app
cat > build/build-info.txt <<INFO
Application : Session 16 Calculator API
Version     : ${APP_VERSION:-1.0.0}
Git commit  : ${GITHUB_SHA:-local}
Built by    : ${GITHUB_ACTOR:-vivek}
Build date  : $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Build status: SUCCESS
INFO
echo ""
echo "Build files:"
ls -la build
echo ""
cat build/build-info.txt
echo ""
echo "Build completed successfully."
