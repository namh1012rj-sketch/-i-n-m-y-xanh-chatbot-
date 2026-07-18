import asyncio
from llm_agent import DMXAgent

async def main():
    agent = DMXAgent()
    print("Agent initialized.")
    async for chunk in agent.send_message_stream("trong phan khuc 10 trieu thi toi nen chon android hay iphone hon"):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
