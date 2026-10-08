//const tokens = require("../fixtures/tokens.json")



beforeEach('Faz o login em cada teste', ()=>{
  cy.login();
  
  
})

function retorna_id_historia_de_usuario(){
return cy.request({
        method: 'GET',
        url: 'userstories?project=29&status__is_archived=false',
        headers: {
            'Authorization':"Bearer "+ Cypress.env('token')
        }
    }).then((resposta)=>{  
    
      //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
      expect(resposta.status).to.be.equal(200)
      //Verifica se o corpo da resposta da requisição não está vazia
      expect(resposta.body).is.not.empty

      //Pega a primeira história
      const historia_id = resposta.body[0].id;
     return cy.wrap({historia_id})

    })
}


function retorna_id_comentario(){
return retorna_id_historia_de_usuario().then(({ historia_id}) => {
return cy.request({
        method: 'GET',
        url: 'history/userstory/'+historia_id+'?type=comment',
        headers: {
            'Authorization':"Bearer "+ Cypress.env('token')
        }
    }).then((resposta)=>{  
    
      //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
      expect(resposta.status).to.be.equal(200)
      //Verifica se o corpo da resposta da requisição não está vazia
      expect(resposta.body).is.not.empty

      //Pega o primeiro comentário
      const comentario_id = resposta.body[0].id;

      cy.log(`Usando o id buscado: ${historia_id}`);
     return cy.wrap({comentario_id})

    })
})

}

describe('Teste de API nos endpoints de comentários', ()=> {

    //POST 
    it('Verificação da criação de uma reação (emoji)', () => {

    retorna_id_comentario().then(({ comentario_id}) => {

        cy.request({
            method: 'POST',
            url: '/comments/'+comentario_id+'/reactions/add_reaction/',
            headers: {
                'Authorization':"Bearer "+ Cypress.env('token')
            },
            body: 
            {
              "emoji": "😍"
            }
            //💯 😍
        }).then((resposta)=>{  
        
          //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
          expect(resposta.status).to.be.equal(200)
          //Verifica se o corpo da resposta da requisição não está vazia
          expect(resposta.body).is.not.empty

        })

        cy.request({
          method: 'POST',
          url: '/comments/'+comentario_id+'/reactions/add_reaction/',
          headers: {
              'Authorization':"Bearer "+ Cypress.env('token')
          },
          body: 
          {
            "emoji": "💯"
          }
        
        }).then((resposta)=>{  

        //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
        expect(resposta.status).to.be.equal(200)
        //Verifica se o corpo da resposta da requisição não está vazia
        expect(resposta.body).is.not.empty

        })

        })//------------ fim da função------------------
    })

    //DELETE com o POST
    it('Verificação da deleção de uma reação (emoji)', () => {

    retorna_id_comentario().then(({ comentario_id}) => {

      cy.request({
        method: 'DELETE',
        url: '/comments/'+comentario_id+'/reactions/remove_reaction/',
        headers: {
            'Authorization':"Bearer "+ Cypress.env('token')
        },
        body:
        {
          "emoji": "💯"
        }
    }).then((resposta)=>{  
    
      //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
      expect(resposta.status).to.be.equal(200)
      //Verifica se o corpo da resposta da requisição não está vazia
      expect(resposta.body).is.not.empty

      

        })
    })//------------------------------

    })

    //GET 
    it('Verificação da listagem de todas as reações (emojis)', () => {
    retorna_id_comentario().then(({ comentario_id}) => {  
      
      cy.request({
        method: 'GET',
        url: '/comments/'+comentario_id+'/reactions/list_reactions/',
        headers: {
            'Authorization':"Bearer "+ Cypress.env('token')
        }
    }).then((resposta)=>{  
    
      //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
      expect(resposta.status).to.be.equal(200)
      //Verifica se o corpo da resposta da requisição não está vazia
      expect(resposta.body).is.not.empty

      expect(resposta.body["😍"]).to.have.property("count")
      
        })
    })//------------------------------
    })

    //POST 
    it('Inserção de um comentário sem ser membro do projeto', () => {

      retorna_id_historia_de_usuario().then(({ historia_id}) => {
        
      cy.log(`Ari: ${historia_id}`);
      cy.request({
        method: 'PATCH',
        url: 'userstories/'+historia_id,
        headers: {
            'Authorization':"Bearer "+ Cypress.env('token')
        },
        body:{
          
        "comment": "TESTE",
        "version": 2

        }
    }).then((resposta)=>{  
    
      //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
      expect(resposta.status).to.be.equal(200)
      //Verifica se o corpo da resposta da requisição não está vazia
      expect(resposta.body).is.not.empty


       })
    })//------------------------------

    })

    //POST 
    it('Verificação do rate limit que consiste no mecanismo de controle para limitar o número de requisitção ', () => {
    retorna_id_comentario().then(({ comentario_id}) => {  

      for(let i = 0;i<10;i++){
        cy.wait(100)
        cy.request({
          method: 'POST',
          url: '/comments/'+comentario_id+'/reactions/add_reaction/',
          headers: {
              'Authorization':"Bearer "+ Cypress.env('token')
          },
          body: 
          {
            "emoji": "💯"
          }
        
      }).then((resposta)=>{  
      
        //Verifica se a resposta deu 200 que indica que a requisição foi bem-sucedida
        expect(resposta.status).to.be.equal(200)
        //Verifica se o corpo da resposta da requisição não está vazia
        expect(resposta.body).is.not.empty

      })
  }
    })//------------------------------
})







})
