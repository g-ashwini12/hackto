import unittest
from services.api.app.orchestrator.graph import legal_graph
from services.api.app.services.inference import MockInferenceClient
import services.api.app.services.inference as inference_module
import services.api.app.orchestrator.nodes as nodes_module
import os

class TestPhase4(unittest.TestCase):
    def setUp(self):
        inference_module.inference_client = MockInferenceClient()
        nodes_module.inference_client = MockInferenceClient()

    def test_safety_validation(self):
        class ForbiddenMockClient(MockInferenceClient):
            def generate(self, prompt, system=None):
                # To pass safety but fail grounding, this would be hard.
                # To test safety, we need grounding to pass.
                return "This is a rental agreement. It is definitely illegal and you will win."

        nodes_module.inference_client = ForbiddenMockClient()

        doc_path = "test_safe.txt"
        with open(doc_path, "w") as f:
            f.write("This is a rental agreement. It is definitely illegal and you will win.")

        inputs = {
            "doc_id": doc_path,
            "user_query": "Is this okay?",
            "is_legal_doc": False
        }

        result = legal_graph.invoke(inputs)
        self.assertIn("Safety Error", result["final_response"])

    def test_grounding_failure(self):
        class HallucinatingMockClient(MockInferenceClient):
            def generate(self, prompt, system=None):
                return "The document says the moon is made of cheese."

        nodes_module.inference_client = HallucinatingMockClient()

        doc_path = "test_ground.txt"
        with open(doc_path, "w") as f:
            f.write("This is a standard rental agreement.")

        inputs = {
            "doc_id": doc_path,
            "user_query": "What is the moon made of?",
            "is_legal_doc": False
        }

        result = legal_graph.invoke(inputs)
        # Off-topic questions now stop at the coverage check with a "document is silent" answer.
        self.assertTrue(result.get("document_silent"))
        self.assertIn("silent", result["final_response"])

if __name__ == "__main__":
    unittest.main()
