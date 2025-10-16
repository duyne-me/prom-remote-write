FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o mock-exporter .

FROM alpine:3.19
WORKDIR /app
COPY --from=builder /app/mock-exporter .
COPY config.yml .
EXPOSE 2112
ENTRYPOINT ["./mock-exporter"]
