package main

import (
	"log"

	"github.com/cryptobench/vm-on-golem/central-discovery-server/internal/discovery"
)

func main() {
	config, err := discovery.LoadConfig()
	if err != nil {
		log.Fatalf("invalid central discovery config: %v", err)
	}
	server := discovery.NewServer(config)
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("central discovery server stopped: %v", err)
	}
}
