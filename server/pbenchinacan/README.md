# Private CA

The "pbench in a can" build of the Pbench Server relies on a private
Certificate Authority cert called `pbench_CA.crt`. This expires at 5
year intervals and needs to be periodically regenerated:

```
openssl req -x509 -new -nodes \
  -key server/pbenchinacan/etc/pki/tls/private/pbench_CA.key \
  -sha256 -days 1826 \
  -out server/pbenchinacan/etc/pki/tls/certs/pbench_CA.crt \
  -subj '/CN=pbench.redhat.com/C=US/L=Westford, MA'
```

Note that the private key file doesn't need to be regenerated.

You can view the current certificate with

```
openssl x509 -text \
  -in server/pbenchinacan/etc/pki/tls/private/certs/pbench_CA.crt
```
