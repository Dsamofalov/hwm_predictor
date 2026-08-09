#include "hwm/http_server.hpp"
#include <string>
int main(int argc,char**argv){uint16_t p=38471;if(argc>1)p=(uint16_t)std::stoi(argv[1]);hwm::SessionStore s;hwm::HttpServer h("127.0.0.1",p,s);return h.run();}
