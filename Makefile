CFLAGS = -O0

app: main.o helper.o
	gcc main.o helper.o -o app

main.o: main.c config.h helper.h
	gcc $(CFLAGS) -c main.c -o main.o

helper.o: helper.c helper.h
	gcc $(CFLAGS) -c helper.c -o helper.o

.PHONY: test clean
test: app
	sh tests.sh

clean:
	rm -f app main.o helper.o
