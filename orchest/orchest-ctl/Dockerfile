FROM jupyter/minimal-notebook:04f7f60d34a6

RUN python3 -m pip install docker

USER root

RUN mkdir -p /orchest/orchest/orchest-ctl
COPY ./ /orchest/orchest/orchest-ctl/

WORKDIR /orchest/orchest/orchest-ctl/app

ENTRYPOINT ["python3", "main.py"]
