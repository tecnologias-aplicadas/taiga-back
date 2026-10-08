/*      
  tipos de atividades:
    "issue",
    "userstory",
    "task",
    "epic"

  
  tipos de relacionamentos:
    RELATED_TO= "RT",
    BLOCKS = "BK",
    BLOCKED_BY = "BKBY",
    DEPENDS_ON = "DPON", 
    DEPENDS_ME = "DPME", 
    DUPLICATED_BY = "DUBY"
    DUPLICATED_FROM = "DUFROM",
    DISCOVERD_WHILE_TESTING = "DWT"


  */

export function criacao_relacionamento_entre_cards(
  projeto_id,
  tipo_origem,
  origem_id,
  tipo_destino,
  destino_id,
  tipo_relacionamento,
  failOnStatusCode = true,
) {
  /* "project_id": projeto_obj[12].id,
                          "source_type": "issue",
                          "source_id": issue_obj[0].id,
                          "target_type": "task",
                          "target_id": task_obj[0].id,
                          "relation_type": "BK"*/

  //Criando o relacionamento entre as tasks
  return cy.request({
    method: "POST",
    url: "/card-relations",
    headers: {
      Authorization: "Bearer " + Cypress.env("token"),
    },
    failOnStatusCode,
    body: {
      project_id: projeto_id,
      source_type: tipo_origem,
      source_id: origem_id,
      target_type: tipo_destino,
      target_id: destino_id,
      relation_type: tipo_relacionamento,
    },
  });
}

export function atualizacao_relacionamento_entre_cards(metodo,projeto_id,tipo_origem, origem_id, tipo_destino, destino_id, tipo_relacionamento, failOnStatusCode = true, options = {}) {
  return retorna_relacionamentos_ativos(projeto_id).then((ids) => {
    expect(ids).to.be.an("array").and.not.be.empty;
    //Atualizamdo o relacionamento entre as tasks
    cy.log("ID do relacionamento selecionado: " + ids[0]);

    const bodyPadrao = {
      project_id: projeto_id,
      source_type: tipo_origem,
      source_id: origem_id,
      target_type: tipo_destino,
      target_id: destino_id,
      relation_type: tipo_relacionamento,
    };

    return cy.request({
      method: metodo,
      url: "/card-relations/" + ids[0],
      headers: {
        Authorization: "Bearer " + Cypress.env("token"),
      },
      failOnStatusCode,
      body: {
        ...bodyPadrao,
        ...options,
      },
    });
  });
}

export function listagem_dos_relacionamentos() {
  return cy
    .request({
      method: "GET",
      url: "/card-relations",
      headers: {
        Authorization: "Bearer " + Cypress.env("token"),
      },
    })
    .then((resposta) => {
      expect(resposta.status).to.eq(200);

      const ids = [];

      resposta.body.forEach((item) => {
        if (item.is_active === true) {
          ids.push(item.id);
          cy.log("ID ativo - sem deleção " + item.id);
        }
      });

      Cypress.env("ids_relacoes", ids);

      // retorna os ids para uso em encadeamento
      return cy.wrap({ ids });
    });
}

export function deletar_relacionamentos() {
  const ids = Cypress.env("ids_relacoes");

  // proteção para evitar erro silencioso
  if (!ids || ids.length === 0) {
    cy.log("Nenhum relacionamento para deletar");
    return cy.wrap([]);
  }

  return cy
    .wrap(ids)
    .each((id) => {
      cy.request({
        method: "DELETE",
        url: `/card-relations/${id}`,
        headers: {
          Authorization: "Bearer " + Cypress.env("token"),
        },
      }).then((resposta) => {
        expect(resposta.status).to.be.oneOf([200, 204]);
        cy.log("Relacionamento deletado: " + id);
      });
    })
    .then(() => {
      // limpa o env após deletar
      Cypress.env("ids_relacoes", []);
      return ids;
    });
}

export function limpeza_relacionamentos() {
  //Limpeza de todos os relacionamentos com base na listagem dos relacionamentos ativos
  listagem_dos_relacionamentos().then((ids) => {
    expect(ids).to.not.be.empty;
    deletar_relacionamentos();
  });
}

export function retorna_relacionamentos_ativos(id_projeto){
  return cy.request({
    //endpoint para listar todas as tarefas de um projeto selecionado pelo id
    method: 'GET',
    url: '/card-relations/list_active?project='+id_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
   //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty
    const ids = [];

    resposta.body.forEach(item => {
      //Adicionando cada id ativo em um vetor [id, id, ..., id]
      ids.push(item.id);
      cy.log('ID ativo ' + item.id);
      
    });
  //retorna somente os ids
 return cy.wrap(ids);
})
}

