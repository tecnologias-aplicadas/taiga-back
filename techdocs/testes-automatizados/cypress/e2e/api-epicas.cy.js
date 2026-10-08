import { criar_epic} from "../support/utils/projetos.js"

beforeEach('Faz o login em cada teste', ()=>{
  cy.login()
})

describe('Teste de API no endpoint épicas', ()=> {

  it('Teste de criação de uma épica de forma correta', ()=>{
    criar_epic(6).then((epic_obj)=>{
       cy.log(`Objeto da epica: ${epic_obj}`);
    })
  })


//POST 
it('Verificação da criação de uma épica', () => {

  cy.request({
    method: 'POST',
    url: '/epics',
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body: 
    {
      "color": "#70728F",
      "status": 26,
      "tags": [],
      "subject": "nova épica Cinthia",
      "description": "teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição",
      
      //da o erro A data está no formato errado. Use um desses no lugar: YYYY[-MM[-DD]]"
      "start_date": "2025-08-05T03:00:00.000Z",
      "expected_completion_date": "2025-08-09T03:00:00.000Z",

      //    "start_date": "2025-08-05T03:00:00.000Z".split('T')[0],
      // "expected_completion_date": "2025-08-09T03:00:00.000Z".split('T')[0],
      "project": 6,
      "team_requirement": true
  }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(201)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty

 

})

})

// Pega o dia de hoje
const hoje = new Date();

// Cria uma nova data com 3 dias a menos
const tresDiasAtras = new Date();
tresDiasAtras.setDate(hoje.getDate() - 3);

// Exibe as datas no console
console.log("Hoje: ", hoje.toDateString());
console.log("Três dias atrás: ", tresDiasAtras.toDateString());

//POST 
it('Verificação da validação da data de início é menor que a data de fim de uma épica', () => {

  cy.request({
    method: 'POST',
    url: '/epics',
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    },
    body: 
    {
      "color": "#70728F",
      "status": 26,
      "tags": [],
      "subject": "nova épica Cinthia",
      "description": "teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição de uma épica teste de descrição",
      "start_date": hoje,
      "expected_completion_date": tresDiasAtras,
      "project": 6,
      "team_requirement": true
  },
  failOnStatusCode: false
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(400)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty
  expect(resposta.body
    .__all__[0]).to.be.equal("The expected completion date must be after the start date.")
  

})

})

//GET 
it('Verificação da listagem de todas as épicas', () => {
  cy.request({
    method: 'GET',
    url: '/epics',
    headers: {
        'Authorization':"Bearer "+Cypress.env('token')
    }
}).then((resposta)=>{  
 
  //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
  expect(resposta.status).to.be.equal(200)
  //Verifica se o corpo da resposta da requisição não está vazia
  expect(resposta.body).is.not.empty


})

})

})
