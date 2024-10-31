up:
# build image and start the service
	sudo -E docker-compose up -d

update:
# fetch remote updates, rebuild image and restart the service
	git pull
	sudo -E docker-compose up --build -d
