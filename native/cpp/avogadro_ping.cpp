// POSIX, READ-ONLY Avogadro JSON-RPC 2.0 proof: length-prefixed internalPing.
// Never sends untrusted plugin commands. Linux/macOS only.
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <regex>
#include <sys/time.h>
#include <string>

static void transfer(int fd, char *ptr, size_t length, bool outgoing) {
    while (length) {
        ssize_t n = outgoing ? ::send(fd, ptr, length, 0) : ::recv(fd, ptr, length, 0);
        if (n <= 0) throw std::runtime_error(outgoing ? "send failed" : "receive failed");
        length -= static_cast<size_t>(n); ptr += n;
    }
}
int main() {
    const char *tmp = std::getenv("TMPDIR");
    const std::string name = std::string(tmp ? tmp : "/tmp/") + ((tmp && std::strlen(tmp) && tmp[std::strlen(tmp)-1] == '/') ? "avogadro" : "/avogadro");
    if (name.size() >= sizeof(sockaddr_un::sun_path)) {std::cerr << "socket path too long\n";return 2;}
    int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {std::cerr<<"socket unavailable\n";return 2;}
    try {
        timeval time_limit{}; time_limit.tv_sec = 4;
        ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &time_limit, sizeof(time_limit));
        ::setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &time_limit, sizeof(time_limit));
        sockaddr_un addr{}; addr.sun_family = AF_UNIX;
        std::memcpy(addr.sun_path,name.c_str(),name.size()+1);
        if (::connect(fd,reinterpret_cast<const sockaddr*>(&addr),sizeof(addr)) != 0) throw std::runtime_error("Avogadro native socket is not available");
        std::string request = R"({"jsonrpc":"2.0","id":1,"method":"internalPing","params":{}})";
        uint32_t len = htonl(static_cast<uint32_t>(request.size()));
        transfer(fd,reinterpret_cast<char*>(&len),4,true);
        transfer(fd,request.data(),request.size(),true);
        uint32_t header=0;
        transfer(fd,reinterpret_cast<char*>(&header),4,false);
        size_t n=ntohl(header);
        if (n > 1'000'000) throw std::runtime_error("reply too large");
        std::string response(n,'\0');
        transfer(fd,response.data(),n,false);
        if (!std::regex_search(response,std::regex(R"("jsonrpc"\s*:\s*"2\.0")")) ||
            !std::regex_search(response,std::regex(R"("id"\s*:\s*1\b)")) ||
            !std::regex_search(response,std::regex(R"("result"\s*:\s*"pong")")) ||
            std::regex_search(response,std::regex(R"("error"\s*:)")))
            throw std::runtime_error("unexpected JSON-RPC ping reply (not a pong)");
        std::cout << response << '\n';
        ::close(fd);return 0;
    } catch (const std::exception& e) {std::cerr<<"NOT_RUN: "<<e.what()<<'\n';::close(fd);return 1;}
}
