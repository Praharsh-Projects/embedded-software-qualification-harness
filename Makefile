.PHONY: host-test qualification firmware acceptance

host-test:
	./scripts/verify.sh host

qualification: host-test

firmware:
	./scripts/verify.sh arm

acceptance:
	./scripts/verify.sh all
