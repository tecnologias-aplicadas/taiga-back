//Obtêm dados dos projetos para os testes
import { retorna_epics,retorna_issues, retorna_projetos, retorna_tasks, retorna_userstorys} from "../support/utils/projetos.js";
//CRUD depedência entre os cards
import {criacao_relacionamento_entre_cards, atualizacao_relacionamento_entre_cards, listagem_dos_relacionamentos, deletar_relacionamentos, limpeza_relacionamentos, retorna_relacionamentos_ativos } from "../support/utils/dependencias-cards.js"

//id_projeto sendo utilizado de forma global em todos os testes abaixo
let id_projeto;

beforeEach("Faz o login em cada teste",() => {
 cy.login();
})



after("Após todos os testes, faz a limpeza dos relacionamentos criados", () => {
  //Limpeza dos relacionamentos para reutilizar os cards de testes para os próximos testes dentro de um único describe 
  // e não tendo a necessidade de rodar todos os testes até chegar no último que faz a deleção de todos as dependências
 // limpeza_relacionamentos();
});

describe("Listagem de dependências entre cards ", () => {
  //GET
  it("Verificação da listagem de dependências entre cards do relacionamento", ()=>{
   retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        cy.request({
          method: "GET",
          url: `/card-relations/get_all_by_ref?project=${id_projeto}&card_type=task&card_ref=${task_obj[1].ref}`,
          headers: {
            Authorization: "Bearer " + Cypress.env("token"),
          },
        }).then((resposta) => {
          expect(resposta.status).to.eq(200);
        });
    }); // func tasks
  })
  })

  //GET
  it("Verificação da listagem de dependências entre cards - dados inválidos card_type", ()=> {
   retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        cy.request({
          method: "GET",
          url: `/card-relations/get_all_by_ref?project=${id_projeto}&card_type=VALOR INVÁLIDO&card_ref=${task_obj[0].ref}`,
          headers: {
            Authorization: "Bearer " + Cypress.env("token"),
          },
          failOnStatusCode: false,
        }).then((resposta) => {
          expect(resposta.status).to.eq(400);
          expect(resposta.body.detail[0]).to.be.equal("invalid_card_type");
        });
      });
    });
  });

  //GET
  it("Verificação da listagem de dependências entre cards- dados inválidos card_ref", ()=> {
   retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then( ({ task_obj }) => {
        cy.request({
          method: "GET",
          url: `/card-relations/get_all_by_ref?project=${id_projeto}&card_type=issue&card_ref=VALOR INVÁLIDO`,
          headers: {
            Authorization: "Bearer " + Cypress.env("token"),
          },
          failOnStatusCode: false,
        }).then((resposta) => {
          expect(resposta.status).to.eq(400);
          expect(resposta.body.detail[0]).to.be.equal("invalid_card_ref_param")
        });
      });
    });
  });

  //GET
  it("Verificação da listagem de dependências entre cards - dados inválidos project",  ()=> {
   retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        cy.request({
          method: "GET",
          url: `/card-relations/get_all_by_ref?project=VALOR INVÁLIDO&card_type=issue&card_ref=${task_obj[0].ref}`,
          headers: {
            Authorization: "Bearer " + Cypress.env("token"),
          },
          failOnStatusCode: false,
        }).then((resposta) => {
          expect(resposta.status).to.eq(400);
          expect(resposta.body.detail[0]).to.be.equal("invalid_project_param")
        });
      });
  });
});

});

describe("Teste de API no relacionamento entre os cards - válido", () => {
  //Relacionamentos de task com task
  //POST
  it("Verificação da criação de um relacionamento task -> task do tipo Relation To - RT", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[1].id}`);

        //Criando o relacionamento entre as tasks
        criacao_relacionamento_entre_cards(
          id_projeto,
          "task",
          task_obj[0].id,
          "task",
          task_obj[1].id,
          "RT",
        ).then((resposta) => {
          expect(resposta.status).to.eq(200);
          expect(resposta.body).to.not.be.empty;
        });
      }); // func tasks
    });
  });

  //POST
  it("Verificação da criação de um relacionamento task -> task do tipo Blocks - BK",()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(
          `TÍTULO da task escolhida - origem: ${task_obj[0].subject} e id: ${task_obj[0].id}`,
        );
        cy.log(
          `TÍTULO da task escolhida - destino: ${task_obj[1].subject} e id: ${task_obj[1].id}`,
        );
        //Criando o relacionamento entre as tasks
        criacao_relacionamento_entre_cards(
          id_projeto,
          "task",
          task_obj[0].id,
          "task",
          task_obj[1].id,
          "BK",
        ).then((resposta) => {
          expect(resposta.status).to.eq(200);
          expect(resposta.body).to.not.be.empty;
        });
      }); // func tasks
    });
  });

  //GET
  it("Verificação da busca de um relacionamento task",  ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_relacionamentos_ativos(id_projeto).then((ids) => {
        cy.log("id do relacionamento selecionado: " + ids[0]);
        cy.request({
          method: "GET",
          url: "/card-relations/" + ids[0],
          headers: {
            Authorization: "Bearer " + Cypress.env("token"),
          },
        }).then((resposta) => {
          expect(resposta.status).to.eq(200);
          expect(resposta.body).to.not.be.empty;
        });
      }); //card relations
    });
  });

  //PUT
  it("Verificação da atualização INTEGRAL de um relacionamento task -> task do tipo Blocked By - BKBY", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(async ({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[0].id}`);
        retorna_relacionamentos_ativos(await id_projeto).then((ids) => {
          cy.log("id do relacionamento selecionado: " + ids[0]);
          //Atualização do relacionamento entre as tasks com dado nulo
          atualizacao_relacionamento_entre_cards(
            "PUT",
            id_projeto,
            "task",
            task_obj[0].id,
            "task",
            task_obj[1].id,
            "BKBY",
          ).then((resposta) => {
            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
          });
        }); // func tasks
    }); //card relations
  });
  });

  //PATCH
  it("(erro PATCH) Verificação da atualização PARCIAL de um relacionamento task -> task do tipo Blocked By - RT", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(async ({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[1].id}`);

        retorna_relacionamentos_ativos(await id_projeto).then((ids) => {
          cy.log("ID do relacionamento selecionado: " + ids[0]);
          cy.request({
            method: "PATCH",
            url: "/card-relations/" + ids[0],
            headers: {
              Authorization: "Bearer " + Cypress.env("token"),
            },
            body: {
              // project_id é campo não editável no PATCH: a API recusa o corpo inteiro
              relation_type: "RT",
            },
          }).then((resposta) => {
            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
          });
        }); // func tasks
      });

      /*  // Atualização do relacionamento entre as tasks com dado nulo
        atualizacao_relacionamento_entre_cards("PATCH",projeto_obj[0].id, {relation_type:"BK"} )
        .then((resposta) => {
         expect(resposta.status).to.eq(200);
         expect(resposta.body).to.not.be.empty;
    });*/
    }); //ids dos card relations
  });

  //Relacionamentos de issue com task
  it("Verificação da criação de um relacionamento issue -> task do tipo Relation To - RT", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_issues(id_projeto).then(async ({ issue_obj }) => {
        cy.log(`id da issue escolhida - origem: ${issue_obj[0].id}`);
        retorna_tasks(await id_projeto).then(({ task_obj }) => {
          cy.log(`id da task escolhida - destino: ${task_obj[0].id}`);

          //Criando o relacionamento entre issue e task
          criacao_relacionamento_entre_cards(
            id_projeto,
            "issue",
            issue_obj[0].id,
            "task",
            task_obj[1].id,
            "RT",
          ).then((resposta) => {
            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
          });
        }); // func tasks
      }); //func issues
    });
  });

  it("Verificação da criação de um relacionamento issue -> task do tipo Blocks - BK",  ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_issues(id_projeto).then( ({ issue_obj }) => {
        cy.log(`id da issue escolhida - origem: ${issue_obj[0].id}`);
        retorna_tasks(id_projeto).then(({ task_obj }) => {
          cy.log(`id da task escolhida - destino: ${task_obj[0].id}`);

          //Criando o relacionamento entre issue e task
          criacao_relacionamento_entre_cards(
            id_projeto,
            "issue",
            issue_obj[0].id,
            "task",
            task_obj[1].id,
            "BK",
          ).then((resposta) => {
            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
          });
        }); // func tasks
      }); //func issues
    });
  });

  //Relacionamentos de issue com epic
  it("Verificação da criação de um relacionamento issue -> epic do tipo Blocks - BK",()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_issues(id_projeto).then(async ({ issue_obj }) => {
        cy.log(`id da issue escolhida - origem: ${issue_obj[0].id}`);
        retorna_epics(id_projeto).then(({ epic_obj }) => {
          cy.log(`id da epic escolhida - destino: ${epic_obj[0].id}`);

          //Criando o relacionamento entre issue e task
          criacao_relacionamento_entre_cards(
            id_projeto,
            "issue",
            issue_obj[0].id,
            "epic",
            epic_obj[0].id,
            "BK",
          ).then((resposta) => {
            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
          });
        }); // func epics
      }); //func issues
    });
  });

  //Relacionamentos de task com userstory
  it("Verificação da criação de um relacionamento issue -> userstory do tipo Depends Me - DPME", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_issues(id_projeto).then(async ({ issue_obj }) => {
        cy.log(`id da issue escolhida - origem: ${issue_obj[0].id}`);

        retorna_userstorys(await id_projeto).then(({ userstory_obj }) => {
          cy.log(`id da userstory escolhida - destino: ${userstory_obj[0].id}`);

          //Criando o relacionamento entre issue e task
          criacao_relacionamento_entre_cards(
            id_projeto,
            "issue",
            issue_obj[0].id,
            "userstory",
            userstory_obj[1].id,
            "DPME",
          ).then((resposta) => {
            expect(resposta.status).to.eq(200);
            expect(resposta.body).to.not.be.empty;
          });
        }); // func userstory
      }); //func issues
    });
  });
});

describe("Teste de API no relacionamento entre os cards - inválido", () => {
  it("Verificação da criação de um relacionamento entre os mesmos cards - ele mesmo", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[0].id}`);

        //Criando o relacionamento entre as tasks
        criacao_relacionamento_entre_cards(
          id_projeto,
          "task",
          task_obj[0].id,
          "task",
          task_obj[0].id,
          "BK",
          false,
        ).then((resposta) => {
          expect(resposta.status).to.eq(400);
          expect(resposta.body).to.not.be.empty;
          expect(resposta.body.code[0]).to.eq("self_relation_not_allowed");
        });
      }); // func tasks
    });
  });

  it("Verificação da criação de um relacionamento que já existe - duplicado", ()=> {
      retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[0].id}`);

        //Criando o relacionamento entre as tasks
        criacao_relacionamento_entre_cards(
          id_projeto,
          "task",
          task_obj[2].id,
          "task",
          task_obj[3].id,
          "BK",
        ).then((resposta) => {
          expect(resposta.status).to.eq(200);
          expect(resposta.body).to.not.be.empty;
        });

        //Criando o relacionamento entre as tasks duplicado
        criacao_relacionamento_entre_cards(
          id_projeto,
          "task",
          task_obj[2].id,
          "task",
          task_obj[3].id,
          "BK",
          false,
        ).then((resposta) => {
          expect(resposta.status).to.eq(400);
          expect(resposta.body).to.not.be.empty;
          expect(resposta.body.code[0]).to.eq("cards_already_related");
        });
      }); // func tasks
    });
  });

  it("Verificação da atualização de um relacionamento entre cards com o tipo de relacionamento nulo", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
    retorna_tasks(id_projeto).then(({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[1].id}`);

        //Atualização do relacionamento entre as tasks com dado nulo
        atualizacao_relacionamento_entre_cards(
          "PUT",
          id_projeto,
          "task",
          task_obj[0].id,
          "task",
          task_obj[1].id,
          null,
          false,
        ).then((resposta) => {
          expect(resposta.status).to.eq(400);
          expect(resposta.body).to.not.be.empty;
        });
      }); // func tasks
    });
  });

  //PATCH
  it("(erro PATCH) Verificação da atualização de um relacionamento task -> task do tipo Blocked By - RT - inválido", ()=> {
    retorna_projetos().then(async (projeto_obj)=>{
     const id_projeto = await projeto_obj[12].id;
      retorna_tasks(id_projeto).then(async ({ task_obj }) => {
        //Primeira e segunda tasks escolhidas
        cy.log(`id da task escolhida - origem: ${task_obj[0].id}`);
        cy.log(`id da task escolhida - destino: ${task_obj[0].id}`);

        retorna_relacionamentos_ativos(await id_projeto).then((ids) => {
          cy.log("id " + ids[0]);
          cy.request({
            method: "PATCH",
            url: "/card-relations/" + ids[0],
            headers: {
              Authorization: "Bearer " + Cypress.env("token"),
            },
            body: {
              project_id: id_projeto,
              source_type: "CINTHIA",
              relation_type: "RT",
            },
            failOnStatusCode: false,
          }).then((resposta) => {
            expect(resposta.status).to.eq(400);
            expect(resposta.body).to.not.be.empty;
            // O PATCH recusa campos read-only antes de validar o conteúdo:
            // source_type e project_id nem chegam ao validador.
            expect(resposta.body._error_code).to.eq("PATCH_READONLY_FIELDS");
            expect(resposta.body.fields).to.include.members(["source_type", "project_id"]);
          });
        }); // func tasks
    }); //card relations
  });
  });
});

//SOFT DELETE
describe("Verificação da deleção dos relacionamentos", () => {
  it("Verificação da listagem dos relacionamentos entre cards", ()=> {
    cy.request({
      method: "GET",
      url: "/card-relations",
      headers: {
        Authorization: "Bearer " + Cypress.env("token"),
      },
    }).then((resposta) => {
      expect(resposta.status).to.eq(200);
      //expect(resposta.body).to.not.be.empty;

      //Salva os ids das relações
      const ids = [];
      resposta.body.forEach((item) => {
        if (item.is_active == true) {
          ids.push(item.id);
        }

        ids.forEach((item) => {
          cy.log("ID ativos - sem deleção " + item);
        });
      });
      Cypress.env("ids_relacoes", ids);
    });
  });

  it("Verificação da deleção dos relacionamentos entre cards", ()=> {
    const ids = Cypress.env("ids_relacoes");
    ids.forEach((id) => {
      cy.log(`ID: ${id}`);

      cy.request({
        method: "DELETE",
        url: "/card-relations/" + id,
        headers: {
          Authorization: "Bearer " + Cypress.env("token"),
        },
      }).then((resposta) => {
        expect(resposta.status).to.eq(204);
        expect(resposta.body).to.be.empty;
        //  "detail": "Relação já foi resolvida."
      });
    }); //for
  });
});
