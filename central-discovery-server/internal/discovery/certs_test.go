package discovery

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestInspectIPCertificateAcceptsMatchingIPSAN(t *testing.T) {
	certPath, keyPath := writeTestIPCertificate(t, "127.0.0.1", 5*24*time.Hour)

	result := inspectIPCertificate(certPath, keyPath, "127.0.0.1", 48*time.Hour)
	if !result.valid || !result.usable {
		t.Fatalf("expected valid certificate, got %#v", result)
	}
}

func TestInspectIPCertificateRejectsWrongIP(t *testing.T) {
	certPath, keyPath := writeTestIPCertificate(t, "127.0.0.1", 5*24*time.Hour)

	result := inspectIPCertificate(certPath, keyPath, "127.0.0.2", 48*time.Hour)
	if result.usable || result.detail != "certificate does not match public IP" {
		t.Fatalf("expected wrong IP rejection, got %#v", result)
	}
}

func TestInspectIPCertificateReportsRenewalDue(t *testing.T) {
	certPath, keyPath := writeTestIPCertificate(t, "127.0.0.1", 2*time.Hour)

	result := inspectIPCertificate(certPath, keyPath, "127.0.0.1", 48*time.Hour)
	if !result.usable || !result.renewalDue {
		t.Fatalf("expected renewal due certificate, got %#v", result)
	}
}

func TestBuildIPCSRIncludesIPSAN(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	csrDER, err := buildIPCSR(key, "127.0.0.1")
	if err != nil {
		t.Fatal(err)
	}
	csr, err := x509.ParseCertificateRequest(csrDER)
	if err != nil {
		t.Fatal(err)
	}
	if len(csr.IPAddresses) != 1 || !csr.IPAddresses[0].Equal(net.ParseIP("127.0.0.1")) {
		t.Fatalf("CSR missing IP SAN: %#v", csr.IPAddresses)
	}
}

func writeTestIPCertificate(t *testing.T, ipAddress string, expiresIn time.Duration) (string, string) {
	t.Helper()
	dir := t.TempDir()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{},
		NotBefore:    utcNow().Add(-time.Minute),
		NotAfter:     utcNow().Add(expiresIn),
		IPAddresses:  []net.IP{net.ParseIP(ipAddress)},
		KeyUsage:     x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment,
	}
	certDER, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	certPath := filepath.Join(dir, "central-discovery-ip.crt")
	keyPath := filepath.Join(dir, "central-discovery-ip.key")
	if err := os.WriteFile(certPath, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certDER}), 0o644); err != nil {
		t.Fatal(err)
	}
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})
	if err := os.WriteFile(keyPath, keyPEM, 0o600); err != nil {
		t.Fatal(err)
	}
	return certPath, keyPath
}
