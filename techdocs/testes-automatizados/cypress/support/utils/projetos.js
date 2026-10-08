//Função para retornar todos os projetos
export async function retorna_projetos(){
  return cy.request({
    //endpoint para listar todos os projetos 
    method: 'GET',
    url: '/projects',
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty
  let pos=0;
  resposta.body.forEach(item => {
    cy.log("pos: "+pos+" id do projeto "+item.id+" nome do projeto: "+item.name)
    pos++;
 })
   // cy.log("meu projeto "+resposta.body[12].id)
    const projeto_obj = resposta.body;
    return cy.wrap({projeto_obj})

 
})
}

export function retorna_tasks(id_projeto){
  return cy.request({
    //endpoint para listar todas as tarefas de um projeto selecionado pelo id
    method: 'GET',
    url: '/tasks?project='+id_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  resposta.body.forEach(item => {
    //cy.log("id da task "+item.id)
 })
    const task_obj = resposta.body;
    return cy.wrap({task_obj})

 
})
}

export function retorna_issues(id_projeto){
  return cy.request({
    //endpoint para listar todas as tarefas de um projeto selecionado pelo id
    method: 'GET',
    url: '/issues?project='+id_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  resposta.body.forEach(item => {
    cy.log("id da issue "+item.id)
 })
    const issue_obj = resposta.body;
    return cy.wrap({issue_obj})

})
}

export function retorna_epics(id_projeto){
  return cy.request({
    //endpoint para listar todas as tarefas de um projeto selecionado pelo id
    method: 'GET',
    url: '/epics?project='+id_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  resposta.body.forEach(item => {
    cy.log("id da epic "+item.id)
 })
    const epic_obj = resposta.body;
    return cy.wrap({epic_obj})

 
})
}

export function retorna_userstorys(id_projeto){
  return cy.request({
    //endpoint para listar todas as tarefas de um projeto selecionado pelo id
    method: 'GET',
    url: '/userstories?project='+id_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  resposta.body.forEach(item => {
    cy.log("id da userstory "+item.id)
 })
    const userstory_obj = resposta.body;
    return cy.wrap({userstory_obj})

 
})
}

export function criar_epic(id_projeto){
  return cy.request({
    //endpoint para criação de uma épica
    method: 'POST',
    url: '/epics?project='+id_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body:{
      
        "color": "#51D3AC",
        "status": 26,
        "tags": [],
        "subject": "nome da épica 2",
        "start_date_ui": "2026-03-09T03:00:00.000Z",
        "expected_completion_date_ui": "2026-04-09T03:00:00.000Z",
        "start_date": "2026-03-09",
        "expected_completion_date": "2026-04-09",
        "project": id_projeto

    }
}).then((resposta)=>{  
 
//Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
expect(resposta.status).to.be.equal(201)
//Verifica se o corpo da resposta da requisição não está vazia
expect(resposta.body).is.not.empty

})

}