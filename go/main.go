package main

import (
	"log"
	"net/http"
	"time"

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

	h := &handlers.APIHandler{DB: conn}
	mux := http.NewServeMux()
	mux.HandleFunc("/events", h.Events)
	mux.HandleFunc("/events/today", h.EventsToday)
	mux.HandleFunc("/events/weekend", h.EventsWeekend)
	mux.HandleFunc("/events/category/", h.EventsByCategory)

	server := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	log.Println("Listening on :8080")
	log.Fatal(server.ListenAndServe())
}
