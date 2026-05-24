#!/usr/bin/env python3
"""
Gera stakeholder map a partir de descrição da feature.
"""
import sys, re

def extract_stakeholders(description):
    # Heurística simples: procura por papeis mencionados
    roles = ["user", "admin", "customer", "seller", "buyer", "manager", "developer", "analyst"]
    found = []
    desc_lower = description.lower()
    for role in roles:
        if role in desc_lower:
            found.append(role)
    return found

if __name__ == "__main__":
    desc = sys.argv[2] if len(sys.argv) > 2 else input("Descrição: ")
    stakeholders = extract_stakeholders(desc)
    print("Stakeholders identificados:", stakeholders)
