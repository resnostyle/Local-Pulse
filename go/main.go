package main

import (
	"log"
	"net/http"

	"local-pulse/go/db"
	"local-pulse/go/handlers"
)

func main() {
	conn, err := db.Connect()
	if err != nil {
		log.Fatalf("db connect: %v", err)
	}
	defer conn.Close()

	if err := conn.Ping(); err != nil {
		log.Fatalf("db ping: %v", err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/events", handlers.Events)
	mux.HandleFunc("/events/today", handlers.EventsToday)
	mux.HandleFunc("/events/weekend", handlers.EventsWeekend)
	mux.HandleFunc("/events/category/", handlers.EventsByCategory)

	log.Println("Listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", mux))
}
