#pragma once
#include "hwm/session.hpp"
#include <atomic>
#include <cstdint>
#include <string>
namespace hwm {
class HttpServer{
public: HttpServer(std::string bind,uint16_t port,SessionStore& store); ~HttpServer(); int run(); void stop();
private: std::string bind_; uint16_t port_; SessionStore& store_; std::atomic<bool> stop_{false};
 std::string handle(std::string method,std::string path,std::string body); static std::string response(int code,std::string body,std::string content_type="application/json");
};
}
