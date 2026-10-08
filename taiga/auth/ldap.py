from ldap3 import Server, Connection, ServerPool, SUBTREE, ALL
from django.conf import settings
from .exceptions import LDAPFallibleConn, LDAPTLSNotDefined
import ast


class LDAPConnectionService(): #LDAPCS00
    def __init__(self) -> None:
        self.__conn = None

    def __enter__(self): #LDAPCS01
        tls = True if settings.LDAPS_TLS.lower() == 'true' else False if settings.LDAPS_TLS.lower() == 'false' else LDAPTLSNotDefined
        servers = [Server(uri, use_ssl=tls) for uri in ast.literal_eval(settings.LDAPS_SERVERS)] #FAZER A VALIDAÇÃO
        server_pool = ServerPool(servers)

        self.__conn = Connection(server_pool, 
                                    user=settings.LDAPS_BIND_DN, 
                                    password=settings.LDAPS_BIND_PASSWORD,
                                    auto_bind=True
                                    )
        return self

    def search_user(self, username): #LDAPCS02
        if self.__conn:
            self.__conn.search(settings.LDAPS_BASE_DN, "("+settings.LDAPS_BASE_SEARCH+"="+username+")", SUBTREE)
            return self.__conn.entries
        else:
            LDAPFallibleConn

    def authenticate(self, username, psswd): #LDAPCS03
        if self.__conn:
            self.__conn.rebind(user=username, password=psswd)
            return self.__conn
        else:
            LDAPFallibleConn
                
    
    def __exit__(self, exc_type, exc_value, traceback): ##LDAPCS03
        if self.__conn:
            self.__conn.unbind()
            self.__conn = None
            

