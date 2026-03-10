# Build stage
FROM golang:1.21-alpine AS builder
WORKDIR /build

# Copy go.mod and go.sum first for better layer caching
COPY go/go.mod go/go.sum ./go/

# Download dependencies
RUN cd go && go mod download

# Copy source and build
COPY . .
RUN cd go && CGO_ENABLED=0 go build -o /server .

# Runtime stage
FROM alpine:3.19
RUN apk add --no-cache ca-certificates
WORKDIR /app

COPY --from=builder /server .
COPY go/templates ./templates
COPY go/static ./static

EXPOSE 8080
CMD ["./server"]
