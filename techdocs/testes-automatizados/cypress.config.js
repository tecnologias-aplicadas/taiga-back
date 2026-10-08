const { defineConfig } = require('cypress')
const env = require('./cypress.env.json');

var data = new Date();
module.exports = defineConfig({

    reporter: 'mochawesome',
    reporterOptions: {
    reportDir: "cypress/report/mochawesome-report",
    overwrite : false,
    json : false,
    html : true,
    timestamp: 'dd-mm-yyyy',

    charts: true,
    reportPageTitle: 'Relatório de Testes do projeto ROF',
    embeddedScreenshots: true,
    inlineAssets: true, // Inclui os assets no próprio relatório HTML
    saveAllAttempts: true, // Salva todos os testes, incluindo os que passaram

    reportFilename: '[name]_data_do__teste_[datetime]'+ '_' + data.getHours() + 'h'+
    data.getMinutes() + 'm' + '_Status_[status]',

    },

    e2e: {


    testIsolation: true,
    defaultCommandTimeout:10000,
    pageLoadTimeout: 10000,
    //Ignorar segurança quando não possui o certificado ssl setar para false, ao testar localhost
    chromeWebSecurity: true,

    // We've imported your old cypress plugins here.
    // You may want to clean this up later by importing these.
    setupNodeEvents(on, config) {
    // return require('./cypress/plugins/index.js')(on, config)

    //Variáveis de ambiente para passar o parâmetro ao abrir o cypress pelo terminal e execução dos testes no ambiente escolhio
    //Ex. npx cypress open --env AMBIENTE=hom
    const ambiente = config.env.AMBIENTE || 'local';
    config.baseUrl = env[ambiente].baseUrl;
    return config;
    },

    },

    env: {
    //interface do cypress-plugin-api 
    requestMode: false,
    hideCredentials: true, 
    hideCredentialsOptions: {
        //headers: ['Authorization'],
        body: ['password']
    }
    }

})
