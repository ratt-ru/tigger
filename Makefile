DOCKER_REPO=radioastro/tigger:1.3.3

.PHONY: build clean

all: build

build:
	docker build -t ${DOCKER_REPO} .

clean:
	docker rmi ${DOCKER_REPO}

upload: build
	docker push ${DOCKER_REPO}
