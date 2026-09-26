# Scripts

O instalador da solução é o `instala.sh` na raiz do repositório.

`inspecionar_servidor.sh` apenas lê o servidor Linux. Não instala nem altera
containers, volumes, redes ou arquivos. A porta verificada é o primeiro
argumento; sem argumento, verifica a `8080`.

`docker/entrada_web.sh` prepara migrações, estáticos e usuários ao iniciar `cge_web`.
`docker/verificar_worker.py` é o healthcheck do Celery worker.
