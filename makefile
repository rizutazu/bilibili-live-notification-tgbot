up:
# build image and start the service
	sudo docker-compose up -d

update:
# fetch remote updates, rebuild image and restart the service
	git pull
	sudo docker-compose up --build -d 
