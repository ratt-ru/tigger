set -e
set -u
WORKSPACE_ROOT="$WORKSPACE/$BUILD_NUMBER"

# build and test
docker build -f ${WORKSPACE_ROOT}/projects/tigger/Dockerfile -t tigger:${BUILD_NUMBER} ${WORKSPACE_ROOT}/projects/tigger/

