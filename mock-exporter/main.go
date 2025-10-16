package main

import (
	"context"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gopkg.in/yaml.v3"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Config structure for YAML input
type Config struct {
	LabelMetrics []map[string]string `yaml:"label_metrics"`
	MockMetrics  []MockMetric        `yaml:"mock_metrics"`
}

type MockMetric struct {
	Name   string            `yaml:"name"`
	Type   string            `yaml:"type"`  // counter | gauge
	Value  float64           `yaml:"value"` // base value
	Labels map[string]string `yaml:"labels"`
}

func loadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var conf Config
	if err := yaml.Unmarshal(data, &conf); err != nil {
		return nil, err
	}
	return &conf, nil
}

func randomDelta() float64 {
	return rand.Float64()*10 - 5 // -5 → +5
}

func runCounter(mock MockMetric) {
	metric := promauto.NewCounter(prometheus.CounterOpts{
		Name:        mock.Name,
		Help:        mock.Name,
		ConstLabels: mock.Labels,
	})
	go func() {
		for {
			inc := rand.Float64() * 5
			metric.Add(inc)
			time.Sleep(time.Duration(2+rand.Intn(3)) * time.Second)
		}
	}()
}

func runGauge(mock MockMetric) {
	metric := promauto.NewGauge(prometheus.GaugeOpts{
		Name:        mock.Name,
		Help:        mock.Name,
		ConstLabels: mock.Labels,
	})
	go func() {
		val := mock.Value
		for {
			val += randomDelta()
			if val < 0 {
				val = 0
			}
			metric.Set(val)
			time.Sleep(time.Duration(2+rand.Intn(3)) * time.Second)
		}
	}()
}

func extractMetrics(cfg *Config) {
	for _, lm := range cfg.LabelMetrics {
		promauto.NewGauge(prometheus.GaugeOpts{
			Name:        "mock_tag_info",
			Help:        "mock_tag_info",
			ConstLabels: lm,
		}).Set(1)
	}

	for _, mm := range cfg.MockMetrics {
		switch mm.Type {
		case "counter":
			runCounter(mm)
		case "gauge":
			runGauge(mm)
		default:
			log.Printf("unknown metric type: %s", mm.Type)
		}
	}
}

func main() {
	rand.Seed(time.Now().UnixNano())

	cfg, err := loadConfig("config.yml")
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	extractMetrics(cfg)

	http.Handle("/metrics", promhttp.Handler())
	http.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte("ok"))
	})

	srv := &http.Server{Addr: ":2112"}

	go func() {
		log.Println("🚀 Mock metrics exporter running on :2112/metrics")
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	// graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)
	<-stop
	log.Println("🛑 shutting down...")
	srv.Shutdown(context.Background())
}
