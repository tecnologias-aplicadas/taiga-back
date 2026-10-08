import {retorna_projetos} from '../support/utils/projetos.js'
//imports e exports
beforeEach('Faz o login em cada teste', ()=>{
  cy.login()
})


export function retorna_id_task(nome_projeto){
  return cy.request({
    //Para rodar local: url: '/projects/by_slug?slug=project-6', 
    //Para rodar no ambiente de testes: url: '/projects/by_slug?slug=projeto-teste-cinthia',
    method: 'GET',
    url: '/projects/by_slug?slug='+nome_projeto,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  resposta.body.task_statuses.forEach(item => {
    cy.log("id do status da task "+item.id)
 })
    const task_statuses_obj = resposta.body.task_statuses;
    return cy.wrap({task_statuses_obj})

 
})
}
//variável global para os testes abaixo no ambiente de testes
const nome_projeto = 'projeto-teste-cinthia';

describe('Teste de API na atualização da porcentagem git das tasks com o peso nos projetos', ()=>{

it('Verificação da atualização da porcentagem de todas as tasks com o valor da coluna alterado', () => {

  retorna_id_task(nome_projeto).then(({ task_statuses_obj }) => {
    
    // Itera por cada objeto dentro do array sem passar pela última posição, pois a última coluna é "fechado" 
    // e não é possível alterar o valor da porcentagem que equivale a 100%((possui validação no back e front)
  for (let i = 0; i<task_statuses_obj.length; i++){

      cy.log(`Coluna  : ${task_statuses_obj[i].name}`);

      cy.request({
        method: 'PATCH',
        url: '/task-statuses/' + task_statuses_obj[i].id,
        headers: {
          'Authorization': "Bearer " + Cypress.env('token')
        },
        body: {
          "completion_percent": 21
        }
      }).then((resposta) => {

        expect(resposta.status).to.eq(200);
        expect(resposta.body).to.not.be.empty;
        expect(resposta.body).to.have.property("completion_percent");
        
        //verifica se não esta fechado, pois se ativo o "is_closed" significa que foi concluído e a porcentagem deve ser 100%
        if(task_statuses_obj[i].is_closed==true){
          cy.log('is_closed: '+task_statuses_obj[i].is_closed)
          expect(resposta.body.completion_percent).to.eq(100);  
        }else{
          cy.log('is_closed: '+task_statuses_obj[i].is_closed)
          expect(resposta.body.completion_percent).to.eq(21); 
        }
        
      });

    }; // fim do for

  });

});


//-------------testes com dados inválidos--------------------------------------------------------------//
it('Verificação da validação da porcentagem com id acima do valor permitido - dados inválidos ', ()=>{
 retorna_id_task(nome_projeto).then(({ task_statuses_obj}) => {
  cy.log("id " +task_statuses_obj)
    for (let i = 0; i<task_statuses_obj.length; i++){

  cy.request({
    method: 'PATCH',
    url: '/task-statuses/'+task_statuses_obj[i].id,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body:{
       "completion_percent": "200"
    },
    failOnStatusCode: false

}).then((resposta)=>{  
 
  //Verifica se a resposta deu 400 que indica que a requisição possui dados inválidos 
  expect(resposta.status).to.be.equal(400)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  expect(resposta.body).to.have.property("completion_percent")

  expect(resposta.body.completion_percent[0]).to.equal("Garanta que o valor é menor ou igual a 100.")


 
})
}; // fim do for

 



})







})

it('Verificação da validação da porcentagem com id abaixo do valor permitido - dados inválidos ', ()=>{
 retorna_id_task(nome_projeto).then(({ task_statuses_obj}) => {
  cy.log("id " +task_statuses_obj)
     for (let i = 0; i<task_statuses_obj.length; i++){

  cy.request({
    method: 'PATCH',
    url: '/task-statuses/'+task_statuses_obj[i].id,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body:{
       "completion_percent": "-10"
    }
,failOnStatusCode: false
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 400 que indica que a requisição possui dados inválidos 
  expect(resposta.status).to.be.equal(400)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  expect(resposta.body).to.have.property("completion_percent")
  expect(resposta.body.completion_percent[0]).to.equal("Garanta que o valor é maior ou igual a 0.")


 
})

}; // fim do for
})



})

it('Verificação da validação da porcentagem com id nulo - dados inválidos ', ()=>{
 retorna_id_task(nome_projeto).then(({ task_statuses_obj}) => {
  cy.log("id " +task_statuses_obj)
  for (let i = 0; i<task_statuses_obj.length; i++){

  cy.request({
    method: 'PATCH',
    url: '/task-statuses/'+task_statuses_obj[i].id,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body:{
       "completion_percent": null
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que foi bem sucedida, no caso é permitido a inserção de nulo, 
  //pois o campo não é obrigatório
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  expect(resposta.body).to.have.property("completion_percent")
  


 
})
}; // fim do for

})


})

it('Verificação da validação da porcentagem com id textual - dados inválidos ', ()=>{
 retorna_id_task(nome_projeto).then(({ task_statuses_obj}) => {
  cy.log("id " +task_statuses_obj)
    for (let i = 0; i<task_statuses_obj.length; i++){

  cy.request({
    method: 'PATCH',
    url: '/task-statuses/'+task_statuses_obj[i].id,
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body:{
       "completion_percent": "teste valor inválido"
    }
  ,failOnStatusCode: false
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 400 que indica que a requisição possui dados inválidos 
  expect(resposta.status).to.be.equal(400)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

  expect(resposta.body).to.have.property("completion_percent")
   expect(resposta.body.completion_percent[0]).to.equal("Insira um número inteiro.")


 
})
}; // fim do for
})

})

})

describe('Teste do is_closed ', ()=>{

    it('Verificação da atualização da porcentagem is_closed true', () => {
      retorna_id_task(nome_projeto).then(({ task_statuses_obj }) => {
        
      
          cy.log(`Coluna  : ${task_statuses_obj[0].name}`);

          cy.request({
            method: 'PATCH',
            url: '/task-statuses/' + task_statuses_obj[0].id,
            headers: {
              'Authorization': "Bearer " + Cypress.env('token')
            },
            body: {
              "completion_percent": 21,
              "is_closed": true
            }
          }).then((resposta) => {

            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
            expect(resposta.body).to.have.property("completion_percent");
            expect(resposta.body.completion_percent).to.eq(100);  
          
            
          });

      

      });

    });

    it('Verificação da atualização da porcentagem is_closed false', () => {
      retorna_id_task(nome_projeto).then(({ task_statuses_obj }) => {
        
      
          cy.log(`Coluna  : ${task_statuses_obj[0].name}`);

          cy.request({
            method: 'PATCH',
            url: '/task-statuses/' + task_statuses_obj[0].id,
            headers: {
              'Authorization': "Bearer " + Cypress.env('token')
            },
            body: {
              "completion_percent": 100,
              "is_closed": false
            }
          }).then((resposta) => {

            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
            expect(resposta.body).to.have.property("completion_percent");
            expect(resposta.body.completion_percent).to.eq(99);  
          
            
          });

      

      });

    });

})