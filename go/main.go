package main

import (
	"html/template"
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

	funcMap := template.FuncMap{
		"formatDateTime": func(t time.Time) string {
			return t.Format("Mon Jan 2, 2006 at 3:04 PM")
		},
	}
	tmpl := template.Must(template.New("").Funcs(funcMap).ParseGlob("templates/*.html"))

	h := &handlers.APIHandler{DB: conn, Tmpl: tmpl}
	mux := http.NewServeMux()
	mux.HandleFunc("/", h.Index)
	mux.HandleFunc("/events", h.EventsHTML)
	mux.HandleFunc("/events/today", h.EventsTodayHTML)
	mux.HandleFunc("/events/weekend", h.EventsWeekendHTML)
	mux.HandleFunc("/events/category/", h.EventsByCategoryHTML)

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
