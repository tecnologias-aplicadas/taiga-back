// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })

// Como para os testes de API e testes e2e necessita na maioria das vezes efetuar o login,
// houve a necessidade de implementar uma função genérica e que pode ser inserida como
// um comando no cypress que pode ser vista em qualquer arquivo, como se fosse uma funcão global.
//
// O usuário de teste é externo (senha local), então entra por /auth/external.
// A rota herdada /auth não existe mais: o login corporativo é /auth/corporate (LDAP).
// O reCAPTCHA só é exigido quando o ambiente está com CAPCHA_USE ligado; o ambiente de
// testes deve rodar com ele desligado, por isso não se envia g-recaptcha-response.

Cypress.Commands.add('login', () => {
    const usuarios = require('../fixtures/usuarios.json');
    return cy.request({
      method: 'POST',
      url: '/auth/external',
      body:
        {
            username: usuarios[0].username,
            password: usuarios[0].password,
        }

  }).should(({ status}) => {
    expect(status).to.equal(200)
   
   }).then(resposta =>{ 
    //Armaneza na variável de ambiente 'token-anm' o valor da resposta da requisição login que é o token de autenticação
    //O token não é registrado em log: ele ficaria gravado no relatório de execução.
    Cypress.env('token',resposta.body.auth_token )
  })
  })


