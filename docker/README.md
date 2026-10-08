# Taiga Docker

## 1. Descrição
Esta pasta contém os arquivos utilizados para a criação de imagens Docker do repositório de **back-end** do Taiga. Essas imagens são usadas nas pipelines de CI/CD, tanto para homologação e produção quanto para a criação de imagens locais.

## 2. Criação de Imagens Locais (Linux)

As imagens locais utilizam o Gunicorn para a execução do projeto, assim como nas imagens oficiais. No entanto, as imagens locais foram ajustadas para exibir logs em nível **Debug** e para realizar atualização automática quando houver modificações nos arquivos do projeto dentro do container.

### 2.1. Clone o repositório

```
git clone -b <nome-da-branch> https://github.com/tecnologias-aplicadas/taiga-back.git
```

### 2.2. Acesse a pasta do projeto

```
cd taiga-back
```
### 2.3. Criar a imagem com o Docker

```
docker build --build-arg AT_TAIGA_CONTRIB_PROTECTED=<access-token> -f docker/Dockerfile-Local -t taiga-back-local:latest .
```

#### 2.3.1. Observações
1. Como os repositórios do TA.DT são privados, é necessário fornecer um access token do GitLab para baixar o repositório [**Taiga Contrib Protected**](https://github.com/celtab/apps-tadt/taigaio/taiga-contrib-protected). Este token pode ser solicitado à equipe do projeto.

2. O nome da imagem e a tag (`taiga-back-local:latest`) podem ser ajustados conforme a sua necessidade.

### 2.4. Configuração no `docker-compose.yml`

Após a criação da imagem local, adicione-a ao seu arquivo `docker-compose.yml`, conforme o exemplo abaixo:

```
services:
...
  taiga-back:
    image: taiga-back-local:latest   ## Imagem Gerada Localmente ##
...
```
---

Para mais informações sobre a execução do projeto em Docker, acesse o repositório [**Taiga Docker**](https://github.com/celtab/apps-tadt/taigaio/taiga-docker).