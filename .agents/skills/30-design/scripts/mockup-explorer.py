#!/usr/bin/env python3
"""
Placeholder para exploração de mockups.
Em produção, integraria com GPT Image ou Figma API.
"""
import argparse

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--feature", required=True)
    p.add_argument("--variants", type=int, default=4)
    args = p.parse_args()
    print(f"Gerando {args.variants} variantes de mockup para {args.feature}...")
    print("[Placeholder: integrar com gerador de imagem ou Figma]")
