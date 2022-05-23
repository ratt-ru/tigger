DOCKER_REPO=radioastro/tigger:1.6.1

.PHONY: build clean

all: build

build:
	docker build -t ${DOCKER_REPO} .

clean:
	docker rmi ${DOCKER_REPO}

upload: build
	docker push ${DOCKER_REPO}
