.PHONY: install dist update publish promote
SHELL=/bin/bash
ECR_REGISTRY=672626379771.dkr.ecr.us-east-1.amazonaws.com
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)


help: ## Print this message
	@awk 'BEGIN { FS = ":.*##"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*##/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:
	pipenv install --dev

update: ## Update all Python dependencies
	pipenv clean
	pipenv update --dev

test: ## Run tests
	pipenv run pytest --cov=manager --cov=mit

tests: test

flake8:
	pipenv run flake8 manager tests mit

safety:
	pipenv check

check: flake8 safety ## Run linting, security checks

coveralls: test
	pipenv run coveralls

dist: ## Build docker container
	docker build -t $(ECR_REGISTRY)/airflow-stage:latest \
		-t $(ECR_REGISTRY)/airflow-stage:`git describe --always` \
		-t airflow .

stage: dist ## Build new container and redeploy staging cluster
	$$(aws ecr get-login --no-include-email --region us-east-1)
	docker push $(ECR_REGISTRY)/airflow-stage:latest
	docker push $(ECR_REGISTRY)/airflow-stage:`git describe --always`
	pipenv run workflow redeploy --yes

prod: ## Deploy current staging build to production
	$$(aws ecr get-login --no-include-email --region us-east-1)
	docker pull $(ECR_REGISTRY)/airflow-stage:latest
	docker tag $(ECR_REGISTRY)/airflow-stage:latest $(ECR_REGISTRY)/airflow-prod:latest
	docker tag $(ECR_REGISTRY)/airflow-stage:latest $(ECR_REGISTRY)/airflow-prod:$(DATETIME)
	docker push $(ECR_REGISTRY)/airflow-prod:latest
	docker push $(ECR_REGISTRY)/airflow-prod:$(DATETIME)
	pipenv run workflow --cluster airflow-prod redeploy --yes
