from abc import ABC, abstractmethod


class ProviderUnavailableError(Exception):
    """
    Raised when the upstream LLM provider is unreachable or returns a
    non-retryable error. Callers MUST catch this and activate degraded mode
    (return retrieved segments with degraded=True) rather than propagating a 5xx.
    """


class LLMProvider(ABC):
    """
    Abstract interface for LLM inference backends.
    Concrete implementations (OpenAI GPT-4o, Anthropic Claude, etc.)
    are injected at runtime.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        context_chunks: list[str],
        user_query: str,
    ) -> str:
        """
        Generate an answer grounded in *context_chunks*.

        :param system_prompt: Role / instruction preamble for the model.
        :param context_chunks: Retrieved text segments to ground the answer.
        :param user_query: The original user question.
        :returns: The generated answer string.
        :raises ProviderUnavailableError: If the upstream LLM cannot be reached
            or returns an unrecoverable error. Callers must handle this by
            returning a degraded response.
        """
