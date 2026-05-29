#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

int main() {
    // 1. Erstellung eines TCP-Sockets (SOCK_STREAM)
    int sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock < 0) {
        perror("Socket-Erstellung fehlgeschlagen");
        return 1;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(80); // Standard-Port für unverschlüsseltes HTTP
    server_addr.sin_addr.s_addr = inet_addr("127.0.0.1"); // Beispiel-IP (Lokaler Host)

    // 2. Verbindung zum Server herstellen
    printf("Verbinde mit dem Server...\n");
    if (connect(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Verbindung fehlgeschlagen");
        close(sock);
        return 1;
    }

    printf("Erfolgreich verbunden!\n");

    // Nach dem erfolgreichen Aufbau würde hier das Senden einer HTTP-Anfrage folgen.

    // 3. Socket ordnungsgemäß schließen
    close(sock);
    return 0;
}
