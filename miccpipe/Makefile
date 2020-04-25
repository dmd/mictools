FSL = /cm/shared/fsl-6.0.1
FSLREQS = $(FSL)/bin/fslroi $(FSL)/bin/flirt $(FSL)/bin/fslmaths $(FSL)/data/atlases/bin/eye.mat
docker :
	cp $(FSLREQS) .
	docker-compose build

clean :
	rm $(notdir $(FSLREQS))

start : docker
	sudo systemctl restart micc-pipeline-container
