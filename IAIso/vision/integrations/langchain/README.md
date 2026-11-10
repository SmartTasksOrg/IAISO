# IAIso v5.0 + LangChain Integration
```python
from langchain.chains import LLMChain
from iaiso.integrations.langchain import IAIsoPressureWrapper

# Wrap with IAIso containment
safe_chain = IAIsoPressureWrapper(
    chain=LLMChain(llm=llm, prompt=prompt),
    pressure_threshold=0.85
)

result = safe_chain.invoke({"input": user_query})
```
