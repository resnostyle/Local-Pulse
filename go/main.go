package main

import (
	"html/template"
	"log"
	"net/http"
	"net/url"
	"strconv"
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
		"derefStr": func(s interface{}) string {
			if s == nil {
				return ""
			}
			if sp, ok := s.(*string); ok && sp != nil {
				return *sp
			}
			return ""
		},
		"pathEscape": func(s string) string {
			return url.PathEscape(s)
		},
		"formatDateTime": func(t time.Time) string {
			return t.Format("Mon Jan 2, 2006 at 3:04 PM")
		},
		"pageURL": func(filterPath string, page int) string {
			if page <= 1 {
				return filterPath
			}
			return filterPath + "?page=" + strconv.Itoa(page)
		},
		"add": func(a, b int) int { return a + b },
		"sub": func(a, b int) int { return a - b },
		"mul": func(a, b int) int { return a * b },
		"seq": func(start, end int) []int {
			if start > end {
				return nil
			}
			s := make([]int, end-start+1)
			for i := range s {
				s[i] = start + i
			}
			return s
		},
	}
	tmpl := template.Must(template.New("").Funcs(funcMap).ParseGlob("templates/*.html"))

	h := &handlers.APIHandler{DB: conn, Tmpl: tmpl}
	mux := http.NewServeMux()
	mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir("static"))))
	mux.HandleFunc("/health", h.Health)
	mux.HandleFunc("/", h.Index)
	mux.HandleFunc("/admin", h.AdminHTML)
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
