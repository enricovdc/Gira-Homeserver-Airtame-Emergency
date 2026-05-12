"""Python reference implementation of the Airtame Emergency Alert logic module.

This package mirrors the semantics of the HSL files in ``module/`` so the wire
protocol, validation rules, and debounce behavior can be unit-tested without a
running Gira HomeServer. The HSL files are the deployed artifact; this Python
port is the executable spec the tests pin behavior against.
"""
