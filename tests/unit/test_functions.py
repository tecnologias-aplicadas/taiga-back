from taiga.auth.functions import user_is_itaipuparquetec

def test_user_is_itaipuparquetec():
    _data = [
        "nome.sobrenome", 
        "nome.sobrenome@itaipuparquetec.org.br", 
        "nome.sobrenome@dominio.com",
        "nome@dominio.org.br",
        "nome",
        "nome.sobrenome@org.br"
    ]
    _expected = [
        True, 
        True, 
        False, 
        False, 
        True, 
        False
    ]

    for input_data, expected in zip(_data, _expected):
        assert user_is_itaipuparquetec(input_data) == expected
