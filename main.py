from src.agent import EmporioAgent


def run_cli():
    print("=" * 65)
    print("   🎸 EMPÓRIO DA MÚSICA - CUSTOMER SERVICE ASSISTANT 🎹")
    print("   Type 'exit' or 'sair' to end the session.")
    print("=" * 65)

    agent = EmporioAgent()
    print("\n[ASSISTANT]: Olá! Seja bem-vindo ao Empório da Música! Como posso te ajudar hoje?\n")

    while True:
        try:
            user_input = input("[YOU]: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "sair", "quit"]:
                print("\n[ASSISTANT]: Obrigado por conversar com o Empório da Música! Até logo! 🎶\n")
                break

            response = agent.answer_customer(user_input)
            print(f"\n[ASSISTANT]:\n{response}\n")
            print("-" * 65)

        except KeyboardInterrupt:
            print("\n\n[ASSISTANT]: Atendimento encerrado. Até mais!")
            break


if __name__ == "__main__":
    run_cli()