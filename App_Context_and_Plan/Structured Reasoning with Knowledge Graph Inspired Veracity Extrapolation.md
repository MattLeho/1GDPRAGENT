# Converted from Structured Reasoning with Knowledge Graph Inspired Veracity Extrapolation.pdf

GIVE: S R K
TRUCTURED EASONING WITH NOWLEDGE
G I V E
RAPH NSPIRED ERACITY XTRAPOLATION
1 2 3 1 2 1
Jiashu He , Mingyu Derek Ma , Jinxuan Fan , Dan Roth , Wei Wang , Alejandro Ribeiro
1
University of Pennsylvania
{jiashuhe,danroth,aribeiro}@seas.upenn.edu
2
University of California, Los Angeles
{mdma,weiwang}@cs.ucla.edu
3
University of California, Berkeley
{jinxuan_fan}@berkeley.edu
A
BSTRACT
Existing retrieval-based reasoning approaches for large language models (LLMs)
heavily rely on the density and quality of the non-parametric knowledge source
to provide domain knowledge and explicit reasoning chain. However, inclusive
knowledge sources are expensive and sometimes infeasible to build for scientific
or corner domains. To tackle the challenges, we introduce Graph Inspired Veracity
Extrapolation (GIVE), a novel reasoning framework that integrates the parametric
and non-parametric memories to enhance both knowledge retrieval and faithful
reasoning processes on very sparse knowledge graphs. By leveraging the external
structured knowledge to inspire LLM to model the interconnections among relevant
concepts, our method facilitates a more logical and step-wise reasoning approach
akin to experts’ problem-solving, rather than gold answer retrieval. Specifically,
the framework prompts LLMs to decompose the query into crucial concepts and
attributes, construct entity groups with relevant entities, and build an augmented
reasoning chain by probing potential relationships among node pairs across these
entity groups. Our method incorporates both factual and extrapolated linkages to
enable comprehensive understanding and response generation. Extensive exper-
iments on reasoning-intense benchmarks on biomedical and commonsense QA
demonstrate the effectiveness of our proposed method. Specifically, GIVE enables
GPT3.5-turbo to outperform advanced models like GPT4 without any additional
training cost, thereby underscoring the efficacy of integrating structured informa-
tion and internal reasoning ability of LLMs for tackling specialized tasks with
limited external resources.
1 INTRODUCTION
Large language models (LLMs) have been shown to be able to generate fluent language, answer
questions and induce knowledge from the given text in recent benchmarks (Ouyang et al., 2022; et al.,
2024a;b; 2022; 2020; Raffel et al., 2020). Though it shows a great performance for general question
answering, we do not see a similar level of success on similar tasks under the scientific domains or
settings that require specialized knowledge tailored to a certain context (Cai et al., 2024; Zhang et al.,
2024; Dorfner et al., 2024; Dong et al., 2023; Zhong et al., 2023; Deng et al., 2024; Ma et al., 2024a).
Two technical disadvantages of LLMs might explain the unsatisfactory performance. On the one
hand, LLMs are not aware of specialized domain knowledge (Ge et al., 2023; Bang et al., 2023; Xie
et al., 2024; Ma et al., 2024b), such as protein-gene relations, drug-disease associations, and actor
profiles of newly introduced movies. The specialized knowledge is not obtained through training and
needs to be constantly updated. On the other hand, LLMs are not equipped to lay out a multi-step
logic chain with domain expertise to identify and solve sub-questions following a correct thinking
process (Wei et al., 2023; Wang et al., 2023; Jiang et al., 2024). For example, to identify whether a
drug is capable of treating a disease, the model needs to figure out the root cause and the affecting
organ of the disease, chemicals that interact with the virus, and the drug formulas that contain the
1
4202
tcO
11
]IA.sc[
1v57480.0142:viXra

correct chemicals. These thinking processes are unique to questions and are hardly presented in
instruction tuning or human preference alignment training data.
Figure 1: Without gold context, Chain-of-Thought (CoT) fails because LLM’s internal knowledge
fails to form a faithful logic chain. Retrieval Augmented Generation (RAG) retrieves semantically
similar but irrelevant information on a sparse KG, leading to hallucination.
Existing works use LLM to guide the factual knowledge search on well-populated external knowledge
structures like knowledge graphs (KG) (Sun et al., 2024; Xu et al., 2024). However, expert-curated
domain-specific knowledge graphs such as UMLS are expensive to obtain and update. Enhancing
LLM reasoning with a sparse external KG is a more realistic and practical setting. Though the
incomplete KGs lack evidence that contributes to problem-solving directly, they encapsulate the
intuition and experience of the curation experts during knowledge structure construction, such as
feasible relation collection and possible connections among similar entities.
In this work, we aim to address vanilla LLMs’ weaknesses in these challenges by proposing GIVE, a
graph-inspired veracity extrapolation framework. GIVE simulates the thinking processes of the KG
constructors and utilizes the structure of KG as inspiration. It populates the sparse KG with silver
edges by receiving hints from factual connections, concretizing the internal knowledge of LLMs,
constructing counterfactual reasoning to combat hallucinations, and additionally retrieving existing
related evidence on KG if needed. GIVE first obtains a focused set of entities that are mostly related
to the question by prompting LLMs. Using the potential relations between the relevant KG concepts,
we construct a reasoning framework all including possible concepts and their potential connections
that could facilitate question answering. We introduce additional intermediate node groups by picking
the multi-step reasoning plans that are most helpful for the ultimate questions. GIVE provides
rich connections among concepts, including factual connections backed by KG evidence, internal
knowledge obtained through pre-training, and novel relations that never appear in the existing data
from the veracity extrapolation process. To complete the reasoning framework, we also include
counterfactual connections among nodes, even if there is no confirmed relation between them, to
prevent hallucination and comprehend the thinking scope. Ultimately, we develop a method that
(1) retrieves external knowledge for more informed question answering; (2) induces a structured
reasoning processes by extrapolating KG triplets to related queried concepts, which we refer to as
“inspiration”.
We experiment with our proposed method on different backbone LLMs on biomedical and common-
sense question answering. We consistently achieved the best performance among all reasoning-based
and retrieval-based baselines. Without any demonstration and additional training cost, our method
enables GPT-3.5T to achieve better or comparable performance on biomedical QA than advanced
GPT4 or GPT-4o-mini, indicating the effectiveness of the proposed framework. Our experiments on
sparse UMLS and ConceptNet showcase the robustness of GIVE in boosting LLM’s reasoning ability
using very limited external knowledge sources in different domains.
2

2 P
RELIMINARIES
Figure 2: Reasoning process comparison between ToG and GIVE. Solid lines are the expert KG
information, dashed lines are the result of our “veracity extrapolation” process. GIVE first builds
an entity group for each queried concepts, then induce inner-group connections using its internal
knowledge. The cross-group connections contained in the KG are treated as evidence to guide LLM
to extrapolate the veracity of such possible relationships between other similar cross-group concepts.
A deep and faithful logic chain ending at the queried entities is thus formed by bridging these
inner-group and cross-group connections. “cell function” in this case is considered as intermediate
entities to facility multi-step reasoning. GIVE is designed to tackle queries in knowledge-intensive
domains with very limited external resource.
Retrieval-Augmented Generation. An LLM p (y∣x) generates the probability distribution of output
θ
y given an input x. RAG-based systems (Lewis et al., 2021) enhance the capability of language
models in knowledge-intensive tasks by leveraging a retriever-generator framework. The retriever
model is denoted as p (z∣x, D), where x is an input query, D is a comprehensive knowledge base,
η
and it generates knowledge distribution over the given input and knowledge base. The generator
p (y∣z, x) then autoregressively generates the output sequence based on the retrieved knowledge z
θ
and the input context x. The likelihood of generating an output sequence y = y can be estimated
∶
1 N
as:
p(y∣x, D) ∶= p (z∣x, D)p (y∣x, z) (1)
η θ
Reasoning on Structured Knowledge Base. Structured knowledge bases like knowledge graphs
(KG) provides better knowledge traceability and correct-ability due to the structured nature of
the knowledge source, thus provides the RAG-framework with better flexibility during knowledge
retrieval. Previous studies encode the KGs (Saxena et al., 2020; Zan et al., 2022) and queries, answer
is generated using similarities between node embedding and query embedding. To contrast, we
propose a one-shot solution for information retrieval from sparse KG and structured reasoning chain
development without any training cost. Recently, ToG (Sun et al., 2024) proposes to iteratively
query LLM to search and prune the optimal knowledge paths to include; GoG (Xu et al., 2024)
decomposes the query into a set of sub-questions and prompts LLM to iteratively solve each of
3

∗
Figure 3: A detailed example of the proposed Veracity Extrapolation process: The gold KG G
contains the gold knowledge set T (x), but is infeasible to build. Directly retrieving knowledge
G∗
T (x) from the accessible KG G results in hallucination. GIVE tackles this challenge by building
G
the augmented entity groups combining KG concepts and queried entity, probing potential relations
across the related concept pairs based on the queried relation and KG relation, then use LLM to prune
the valid factual and counter-factual candidate knowledge, thus prompt LLM to generate faithful
CoT.
them. GNN-RAG (Mavromatis & Karypis, 2024) formulates the answer-extraction process as a node
classification problem over the knowledge graph. These methods, although proved to be effective in
answering queries in specific KG-QA pairs, are built on the assumption that the high-quality data
base that contains the gold knowledge are always accessible and easy to retrieve. In the context of
scientific domains, however, building specific knowledge bases is challenging, because it requires
advances in both domain-specific natural language processing(NLP) and filed-wide vocabulary
standardization (Badal et al., 2019; Verhagen et al., 2012). General knowledge bases like Wikipedia
or Freebase contains tens of millions of irrelevant entities and triplets, thus are time and resource
consuming for LLMs to search from.
Problem Definition. In this paper, we study reasoning-rich domain-specific question answering
using very sparse knowledge graphs. A knowledge graph (KG) is defined as G = {E , R , E },
G G G
E = {(u, r, v), u, v ∈ E , r ∈ R }, where E is the set of entities and R is the set of relations.
G G G G G
An input query x is a statement about the entities E and relations R . For example, the query “Is
x x
melatonian effective for insomnia?” contains entity set E = {melatonian, insomnia} and relation set
x
R = {effective for}.
x
To solve an instance of (G, x), the key step is to retrieve highly-relevant knowledge set from the KG.
Suppose the gold knowledge set T (x) for x in G is the collection of knowledge triplets in G that
G
explicitly contains the ground-truth output for x. Previous works focus on the case when the given
∗
knowledge graph G contains some gold knowledge about x, i.e. G ∈ G . We provide a solution to the
x
∗
general form of KGQA instances (G,x) where G ∉ G , by first combining the parametric memory of
x
LLM and the sparse KG G, query x to expand the entity and relation set to consider, before using the
structure of G to inspire LLM to extrapolate the veracity of the generalised edges among all related
concepts, thus solve the input query. Formally, our approach is formulated as:
˜ ˜
p(y∣x, G) ∶= p (N , R ∣x, G)p (T (G)∣x, N , R )p (y∣x, T (G)) (2)
α x x β x x x γ x
˜
where N and R are the expanded sets of relevant entities and relations, T (G) is an extrapolated
x
knowledge set that combines the external evidence in G and x, and the parametric internal memory
of LLM.
3 GIVE: G -I V E
RAPH NSPIRED ERACITY XTRAPOLATION
Our proposed method prompts faithfully inductive reasoning by 1) Using LLM to decompose the
query into important concepts and attributes; 2) constructing entity groups by combining the key entity
in the query and its relevant concepts in the knowledge graph; 3) inducing inner-group connections
between the queried entity and related concepts using parametric knowledge of LLM; 4) build
inter-group connections by probing and pruning all pairwise possible connections, and considering
intermediate concept groups to facilitate multi-hop reasoning for complicated questions. We present
the overall algorithm for GIVE in Appendix 1 and the prompt and example output in Appendix D.
4

3.1 Q I E
UERY NFORMATION XTRACTION
Given query x, GIVE first leverages the LLM to retrieve the entity and relation sets E and R :
x x
x → LLM → E , R (3)
x x
where E = {e 0 , e 1 ...e n} denotes the top-k concepts, and R = {r 0 , r 1 ...r m} is the top-m relations
x x x x x x x x
or attributes in the query.
3.2 E G C
NTITY ROUP ONSTRUCTION
The goal of this step is to bridge the gap between the limited richness of knowledge base corpus
and the complexity of the potential input. To this end, we search through the knowledge space, to
construct a cluster of similar concepts, for each of the entities that we identified as important for the
given query. For each e k ∈ E , GIVE leverages an underlying pre-trained LM encoder w to encode
x x
the concepts in the knowledge base, and retrieve p most similar concepts to each queried entity by
comparing cosine similarities:
k i i i k
Y = {y , y ...y , } = argmin {cos(w(e ), w(yˆ ))} (4)
x x0 x1 xp p x i
∈
yˆ E
i G
k k k
The set Y contains all entities that are semantically similar to the queried concept e , and e is
x x x
k k
appended to Y to formulate the entity group N :
x x
k k k i k
N = {e } ∪ Y N = {N } (5)
x x x x x i = 1
k
There are two advantages of the entity set N s: (1) Inducing inter-group connections between the
x
queried entity and its “sibling” concepts naturally lead to a reasoning chain on the KG concepts. (2)
It relaxes the strict information retrieval on the few queried entity, to relationship inference over a
larger set of relevant concepts.
3.3 I -
NNER GROUP CONNECTIONS
i
Firstly, considering each N in Section 3.2, we induce connections between each queried entity and
x
its other semantically-similar concepts in its own entity group. The purpose of this step is to inspire
LLM to conduct divergent thinking on the related similar concepts, not only focus on the queried
entity itself. The hard problem of inducing relationships directly between two queried entities is
released to finding any possible relations between two sets of similar concepts.
To this end, we utilize LLM to openly fill in the relationship between the queried entity and each of
the in-group concept. In other words, the richness of corpus of the external knowledge base serves as
an intermediate to inspire the LLM to expand the possible relation set R .
x
3.4 I -
NTER GROUP CONNECTIONS
In this section, we provide evidence for the language model to induce relationships between the
i j
node pairs that cross two entity groups. Given two concept groups N and N , we first identify all
x x
legitimate relations that could be used to connect any node pairs across these two groups, and use
LLM to prune these psedu-connections. We also consider intermediate groups to facilitate multi-hop
reasoning.
3.4.1 P R I
OTENTIAL ELATIONS NDUCTION
Between each pair of entity groups, we consider two kinds of potential relations: (1) Relations
mentioned in the question. The relations asked by the ultimate QA task are the critical connections to
be considered. We induce the relation in questions by prompting the LLM while providing instruction
and examples on identifying relations and the content of the question as input. The relation would be
a sub-sequence of the original question. (2) KG relations that exists between these two groups.
Since each group contains semantically similar concepts, the existing cross-group KG connections
could potentially connect nodes in two node groups with correct semantic meaning.
5

GIVE boosts the reasoning ability of LLM by inspiring it to consider these two kinds of potential
ij
relations, when inducing useful knowledge between two entities. Formally, the potential relations R
x
i j
that could be used to connect the queried entities e and e are the queried relations and the relations
x x
connects their relevant entities in the knowledge graph:
ij
R = {r, (u, r, v) ∈ E , u ∈ N , v ∈ N } (6)
G i j
G
ij ij ij k
R = R ∪ R R = {R } (7)
x x G x x i,j = 1
For example, considering two node groups about “chemical” and “gene”, certain chemicals might
“upregulate” certain genes and another set of chemicals might be “substrate” for some genes. Combin-
ing any relations from the “chemical” group to the “gene” group, we can identify all feasible relations
that could correctly describe the relation between two kinds of nodes according to the knowledge
graph would be a set of relations (“upregulate”, “downregulate”, “agonize”, “antagonize” and “serve
as substrate”). The combined set of potential relations among each pair of entity groups would
facilitate the following process of building connections among nodes.
3.4.2 I N G D M - R
NTERMEDIATE ODE ROUP ISCOVERY FOR ULTI STEP EASONING
Considering only nodes and connections directly related to the ones mentioned in the question would
limit the thinking scope, this is especially the case when dealing with scientific questions when
neither LLM nor the external knowledge source itself has enough information to connect two entity
groups directly. For example, when answering a query about the effect of certain drug to a disease,
a natural reasoning chain is to build the (drug, compound, disease) connections, to form the claim
“because certain compound entity is contained in the drug, and the diseases that can be treated by the
entity, it could be inferred that the drug can treat entity”.
To provide sufficient knowledge and thinking hints for such complicated tasks that require linking
target entities through multi-step reasoning, GIVE explores new node groups as intermediate stopovers
of the thinking process. Firstly, all length-2 paths between two node groups are discovered. Secondly,
LLM is prompted to automatically select the most helpful multi-hop thinking process that benefits the
ultimate question-answering task, where each multi-hop thinking process comes from verbalization
of the length-2 path we discovered. Using the intermediate node of the optimal length-2 path, GIVE
constructs an intermediate entity group by leveraging the same process as illustrated in Section
3.2. Note that the intermediate node group is created to build the multi-hop connections between
two queried entity groups. The intermediate node groups contain a set of similar “intermediate”
entities in the knowledge graph, whereas the queried entity group contains an entity in the query and
semantically similar concepts to the queried entity that are contained in the knowledge graph.
3.4.3 KG-
STRUCTURE GUIDED REASONING
In the previous sections, we pre-process the external structured knowledge source by constructing (1)
groups of important concepts in Section 3.2, and any possible intermediate groups in Section 3.4.2.
(2) possible connections between any two groups in Section 3.4.1. GIVE utilizes these non-parametric
evidence N and R to inspire LLM conduct reasoning using its parametric knowledge, and formally
x x
build the inter-group knowledge set.
Assigning relations with external evidence. If there exists an edge on the external knowledge
graph between a pair of nodes, we directly inherit the ground-truth relation from the original KG
G. We consider all knowledge described on the external KG as ground-truth known facts. When we
verbalize such edge in the prompt, we use affirmative tense to indicate such a fact is true with very
high confidence.
Veracity Extrapolation with internal knowledge. The potential relations between node groups
induced in Section 3.4.1 are crucial to inform us about the possible connections between nodes. The
pre-training stage of LLM equips the model with rich factual knowledge from the unstructured corpus.
It is important to concertize the relevant internal knowledge to affirm the model’s decision or to reject
wrong answers with explicit context. Thus, we prompt the LLM to assign a label to each potential
relation among two node groups: “yes”, “no”, or “maybe”. If the LLM yields “yes” for a certain
relation, it indicates the model is confident that such a claim is factual.
6

It is important for the QA model to know not only what claims are highly likely to be factual but also
the claims that are not going to hold or may not hold. This kind of counterfactual relation information
prevents the model from hallucination. If the node pair does not contain a relation in the potential
relation set indicated by a “no” answer returned by the LLM, we assign a reversed relation. If the
model is not sure about a certain relation using its internal knowledge by answering “maybe”, these
connections are discarded as the LLM is not sure about its validity thus bears a higher chance of
causing hallucination.
Discovering open relations for novel connections. To prevent the potential scope limitation of the
relations presented in the knowledge graph, we additionally prompt the LLM to freely create a short
phrase to describe the relation of a given node pair. Even two nodes can be connected through a novel
relation that not presented in either question or the knowledge graph, the open relation discovery
design keeps the flexibility of our proposed framework.
Finally, we append all (subject, relation, object) triplets that are retrieved from the previous sections
to the input prompt of the question-answering task, and expect the LLM to generate the answer
conditioned on the additional knowledge and intermediate thinking results.
3.5 P
ROGRESSIVE ANSWER GENERATION
From the reasoning process presented in Section 3.4.3, we obtained three kinds of knowledge: (1)
Affirmative knowledge set that contains all inner-group connection; all the potential cross-group
connections that are labeled as “yes” by the LLM; and the connections that are built purely by the
internal knowledge of LLM. (2) Counter-factual knowledge set that contains all the potential relations
that are labeled as “no” by LLM. (3) The ground-truth connection contained in the KG.
To prevent hallucination, we adopt a progressive manner to generate the final answer by first giving
only the affirmative knowledge set. Then we ask the LLM to refine this answer by giving the full
context of the previous step plus the counter-factual knowledge set. The final answer is generated by
providing details of all previous context and the ground-truth knowledge contained in the original
knowledge graph.
4 E
XPERIMENTS
The experiments in this section are designed to answer the following research questions: (1) Is GIVE
able to provide structured high-quality knowledge using very sparse external resources thus result in
higher QA accuracy? We answer this in Section 4.2 by conducting experiments on various biomedical
QA benchmarks using a very sparse UMLS knowledge graph (Li et al., 2023). (2) Is GIVE robust
to different scarcities of KG to retrieve useful information? To this end, we conduct experiments
by randomly sampling different portions of triplets in ConceptNet (Speer et al., 2018), and use the
resulted subgraphs to test on CommonsenseQA (Talmor et al., 2019). (3) Is the performance of GIVE
sensitive to the number of additional concepts in each group (which is the only hyper-parameter
for our method)? We perform ablation studies in Section 4.4 to answer this. (4) On what kind of
questions GIVE achieve the best performance? We give a detailed analysis in Appendix C.1 and
conclude that GIVE improves the performance of LLM by achieving very high accuracy on the
questions where the ratio of expert KG knowledge in the overall retrieved knowledge set is relatively
high. (5) Is there any other factors that may influence the performance of GIVE? We conducted
additional ablation studies of the subset of each dataset in Appendix B.1, B.2 and B.3 on the number
of seeded examples, prompting strategies and encoder model size for entity group construction.
4.1 E
XPERIMENTAL SETTINGS
4.1.1 R - QA
EASONING RICH DATASETS
Since we aim to enable LLM to conduct faithful reasoning utilizing very sparse KG, thus the general
KB-QA pairs with ground truth knowledge path does not align with the purpose of our experiments.
For biomedical reasoning experiments we use a sparse UMLS (Li et al., 2023) with 135 nodes and
5877 edges, test the accuracy on the “yes-no” datasets PubmedQA (Jin et al., 2019) and BioASQ
(Krithara et al., 2023), and multiple-choice dataset Processbank (Berant et al., 2014). In Section 4.3,
7

we test on the validation set of CommonsenseQA (Talmor et al., 2019), using (1) the full English
ConceptNet (Speer et al., 2018) with 844,158 nodes and 2,085,099 edges. (2) 50% edges version with
607,483 nodes and 1,042,550 edges. (3) 10% edges version with 223,863 nodes and 208,510 edges.
We focus on questions that are hard to answer without additional reasoning by ignoring any
“gold” knowledge or context. For PubmedQA (Jin et al., 2019), we challenge the competing methods
by providing LLM with only the question statement and the retrieved facts, not any ground-truth
gold context in which the answer is self-presented. Similarly, for BioASQ (Krithara et al., 2023),
we extract all questions in Task 2B, 3B and 4B with both “ideal answer” (long answer) and “exact
answer” (short answer). We ignore the long answer to test the accuracy on the short answer returned
by each method. In the case of Processbank (Berant et al., 2014), we do not provide the ground-truth
annotations by only giving the question statement and choices.
4.1.2 C LLM
OMPETING BASELINES AND BACKBONE S
We compare the proposed GIVE framework against standard I/O prompting (Brown et al., 2020);
CoT prompting (Wei et al., 2023); text-based RAG (Lewis et al., 2021), following the original
setting to use a DPR-based retriever (Karpukhin et al., 2020) on the verbalized triplets; and ToG
(Sun et al., 2024), which is the SOTA framework for retrieving structured information via KG-LLM
interactions. For each competing method, we compare their performance on GPT3.5-turbo, GPT-4,
GPT4o-mini and Llama3.1-70B-Instruct. For each baseline methods, we provide the same set of
randomly chosen k-shot examples, where k = 5 for “yes-no” datasets PubmedQA and BioASQ,
and k = 10 for multiple-choice datasets ProcessBank and CommonsenseQA. To ensure fairness of
comparison, for CoT, RAG and ToG, we also provide the correct reasoning process for each of the
given examples. We provide the full details of prompts used for each baseline in Appendix D.
As illustrated in Section 3.5, we prompt LLM with the three knowledge sets generated by GIVE
progressively. GIVE uses only the affirmative knowledge set, GIVE prompts LLM with both
a a+c
affirmative and counter-factual knowledge. Finally in GIVE we provide LLM with affirmative
a+c+e
knowledge, counter-factual knowledge and the expert knowledge contained in the knowledge graph.
4.2 B R
IOMEDICAL EASONING
Table 1: Performance on Biomedical QA in accuracy (%) using GPT series backbone models.
Retrieval-based methods are given access to a sparse UMLS KG (Li et al., 2023). Each method
is provided with the same few-shot examples. We highlight in green the largest performance
improvement of the proposed GIVE framework, compared to the (1) best of {I/O prompting (Brown
et al., 2020), CoT prompting (Wei et al., 2023)}, (2) text-based RAG (Lewis et al., 2021), (3) ToG
(Sun et al., 2024).
GPT3.5-turbo GPT4 GPT4o-mini
# Method/Dataset
PubMedQA BioASQ ProcessBank PubMedQA BioASQ ProcessBank PubMedQA BioASQ ProcessBank
Without external knowledge
1 I/O prompt 46.2 43.5 67.3 42.2 88.2 64.8 23.4 88.7 79.4
2 CoT prompt 48.6 63.5 70.9 37.8 80.4 59.3 23.8 79.3 81.4
Text-based retrieval
3 RAG 13.4 40.9 67.3 26.4 24.3 78.9 15.2 16.3 84.9
Graph-based retrieval
4 ToG 17.6 18.0 66.8 19.1 15.4 81.4 21.8 10.1 84.4
Our method
5 GIVE 44.4 82.6 72.9 50.0 90.0 82.7 26.0 89.5 85.9
a
5 GIVE 49.8 86.1 73.9 50.2 80.6 83.3 27.4 81.9 87.4
a+c
5 GIVE 53.6 88.2 73.4 43.4 87.8 82.7 27.2 81.9 86.9
a+c+e
6 Best Gain(+%) 5/40.2/36 24.7/47.3/70.2 3/6.6/7.1 8/23.8/31.1 1.8/9.6/74.6 22.6/8.5/6 3/12.2/5.6 0.8/73.2/79.4 6/2.5/3
GIVE enables smaller-sized LLMs to achieve better performance than the most advanced
models with very limited external knowledge. Our first observation is that GIVE consistently
achieves the best performance among all reasoning and retrieval-based baselines. Especially, GIVE
enables GPT3.5-turbo to surpass GPT4 uniformly on biomedical reasoning tasks. For example, on
BioASQ, GIVE offers GPT3.5-turbo an accuracy boost of 44.7%, resulting in an accuracy that is
8


| GPT3.5-turbo
PubMedQA BioASQ ProcessBank | GPT4
PubMedQA BioASQ ProcessBank |
| --- | --- |

| 46.2 43.5 67.3
48.6 63.5 70.9 | 42.2 88.2 64.8
37.8 80.4 59.3 |
| --- | --- |

| 13.4 40.9 67.3 | 26.4 24.3 78.9 |
| --- | --- |

| 17.6 18.0 66.8 | 19.1 15.4 81.4 |
| --- | --- |

| 44.4 82.6 72.9
49.8 86.1 73.9
53.6 88.2 73.4 | 50.0 90.0 82.7
50.2 80.6 83.3
43.4 87.8 82.7 |
| --- | --- |
| 5/40.2/36 24.7/47.3/70.2 3/6.6/7.1 | 8/23.8/31.1 1.8/9.6/74.6 22.6/8.5/6 |
11.4% higher than GPT4. GIVE achieves this by using a sparse KG of only 135 nodes, without any
additional training cost.
GIVE is flexible to operate on LLMs with dif- Table 2: Performance on Biomedical QA using
ferent sizes and levels of internal knowledge. backbone LLM Llama-3.1.
Comparing the results in Table 1 and Table 2, we
observe that GIVE is able to boost the reason-
Meta-Llama-3.1-70B-Instruct
ing ability of LLMs with different sizes (GPT4 # Method/Dataset
PubMedQA BioASQ ProcessBank
> GPT3.5T > Llama3.1 > GPT4o-mini). Fur-
Without external knowledge
thermore, there are two important factors for
1 I/O prompt 48.0 91.0 85.4
the performance increase offered by GIVE com-
2 CoT prompt 50.4 91.3 84.3
pared to I/O prompt or CoT, the model size and
Text-based retrieval
whether or not it has enough internal knowledge
3 RAG 49.8 45.4 84.4
to answer the questions. Specifically, the larger
Graph-based retrieval
the backbone model is, the higher accuracy in-
4 ToG 38.4 31.0 85.9
crease GIVE is able to offer. We see this by com-
Our method
paring the performance gain on PubMedQA. In
5 GIVE 56.0 91.7 86.4
case of BioASQ and Processbank, I/O prompt-
a
5 GIVE 56.2 91.7 86.9
a+c
ing already achieves an accuracy of around 90%,
5 GIVE 56.0 92.6 86.4
a+c+e
GIVE is still able to increase the performance of
6 Best Gain(+%) 5.8/6.3/17.8 1.3/47.2/61.6 1.5/2.5/1
the model using very limited external evidence.
GIVE effectively prevents hallucination intro-
duced by the sparse knowledge source. We also see that the advantage of GIVE is more significant
compared to the retrieval-based methods that tries to directly use the knowledge retrieved from the
sparse external knowledge source. This is because the triplets retrieved by DPR (Karpukhin et al.,
2020) and ToG (Sun et al., 2024) are low-quality and the model is influenced a lot by these irrelevant
information. We see this from Figure 10 and 9. This is particularly the case when they operate on a
strong model that already has rich internal knowledge (GPT4/4o-mini on BioASQ). It turns out to be
an important problem to prevent such hallucination when deploying LLMs in knowledge-intensive
domains with limited external resource. GIVE provides a low-cost solution to this challenging
scenario, for it is not only robust to hallucination introduced by the irrelevant knowledge, but also
capable of improving the performance, even using very limited expert domain knowledge.
GIVE achieves the most consistent per- Table 3: Performance on CommonsenseQA (Val
a+c+e
formance compared to GIVE and GIVE . set) in accuracy(%) on GPT3.5-turbo. Retrieval-
a a+c
Since GIVE takes use of all the generated based methods are given access to a sub-graph
a+c+e
knowledge as illustrated in Section 3.5. This of ConceptNet (Speer et al., 2018) with different
implies the contour-factual knowledge retrieval portions of randomly sampled triplets.
process we propose in Section 3.4.3 provides
useful additional information to guide reasoning,
Commonsense QA
also underlines the importance of properly incor- # Method / % of triplets
10% 50% 100% (Full)
porating sparse KG information in knowledge-
Without external knowledge
intensive QA tasks. This is further discussed in
1 I/O prompt 71.8
Appendix Section C.1.
2 CoT prompt 72.2
Text-based retrieval
4.3 C OMMONSENSE 3 RAG 70.4 70.6 71.3
R C N
EASONING ON SPARSE ONCEPT ET Graph-based retrieval
4 ToG 69.7 71.2 69.8
Our method
GIVE is effective in retrieving information
from both sparse and dense KG. Regarding 5 GIVE 73.3 73.6 74.2
a
5 GIVE 73.4 73.6 74.2
the ability of GIVE to generate useful informa- a+c
5 GIVE 73.5 73.8 74.7
a+c+KG
tion from both sparse and complete KG, the
6 Best Gain(+%) 1.3/3.1/3.8 1.6/3.2/2.6 2.5/3.4/4.9
conclusion is definite. As we can see from Table
3, on the full ConceptNet, GIVE offers 3.4%
and 4.9% accuracy increase compared to RAG (Lewis et al., 2021) and ToG (Sun et al., 2024).
Retrieving information from very dense KG on a specific domain also poses significant challenge
because of the large number of similar entities and triplets. The results proved the robustness of
GIVE to generate useful information, thus prompting structured reasoning for LLMs using different
scarcities of external knowledge source.
9


| 70.4 | 70.6 |
| --- | --- |

| 69.7 | 71.2 |
| --- | --- |

| 73.3
73.4
73.5 | 73.6
73.6
73.8 |
| --- | --- |
| 1.3/3.1/3.8 | 1.6/3.2/2.6 |
Figure 4: Performance of GIVE with different numbers of entities per group
4.4 A S
BLATION TUDY
GIVE achieves the best performance using only small number of additional KG entities. The
key parameter of GIVE is the number of additional KG entities we introduced to each concept group.
To study how that influences the performance of GIVE, we conduct experiments on biomedical
reasoning with GPT3.5-turbo, using number of KG entities from 0 to 3. As shown in Figure 4, the
performance of GIVE improves first with increasing number of KG entities per group from 0 to 2,
and decreases when we increase it to 3 and the observation is uniform across all datasets. This is
because GIVE first enables LLM to conduct structured reasoning using the additional information.
Since we are using a sparse KG with only 135 nodes, when k is greater than 2, it is very likely to
introduce entities that is not directly related to the queried concepts, and thereby causes hallucination.
Get inspired, do not recite. The performance jump when increasing the number of KG entities
from 0 to 1 proves the effectiveness of the “Graph Inspiration” process we proposed in Section
3.4.3, by introducing additional related concepts from external source and “inspire” the LLM to
conduct divergent reasoning using these external clues. This points out that the ability of divergent
thinking of LLMs may have long been ignored, as we have been focusing on retrieving the gold
knowledge for the model to “recite”. Instead, further studies should be conducted on how to utilize
the external knowledge as a high-level clue to “inspire” LLMs conduct reasoning, rather than a
“long-answer” style gold context. This is especially the case when we deploy LLMs using limited
external knowledge. Intelligent agents should not recite the context, they get inspired from the
external clue and conduct faithful reasoning.
5 L S
IMITATION TATEMENT
It remains a heuristic on how to eliminate hallucination caused by in-accurate knowledge GIVE
introduced, as there is no performance guarantee on the LLM’s ability to prune out the correct
potential knowledge from the wrong. In fact, it is related to the size of the LLM and how extensively
it has been trained on the specific domain knowledge. Regarding the complexity of GIVE, suppose
we have m entity groups and each group has n concepts, between two entity groups there r candidate
relations. The inner-group connections (Section 3.3) takes O(mn) LLM calls. For inter-group
connections (Section 3.4.3), the number of LLM calls needed equal to the number of generalized
potential connections, which is O(rm 2 n 2). However, as shown in Section 4.4, GIVE achieves best
performance when n = 1 or 2. In Appendix C.2 we further prove that (1) average value for m is
around 3 for biomedical reasoning datasets and 4 for CommonsenseQA; (2) average value for r is
upper-bounded by 4 for all datasets; (3) complexity of GIVE can be further reduced by pruning
candidate knowledge in batches. For example, if we give 5 candidate relations between two concepts
in one prompt, and let LLM decide which ones are true or false, this will reduce the number of LLM
calls approximately 80%.
6 C
ONCLUSION
We propose Graph Inspired Veracity Extrapolation (GIVE), a knowledge extrapolation framework
for structured reasoning of LLM on sparse knowledge graphs. GIVE neither focuses on explicit
10

information retrieval, nor relies on improving the internal reasoning ability of LLMs by appending
triggering statements to the query. It utilizes the high-level thinking processes mined in sparse
knowledge graphs to combine both approaches. It retrieves the most relevant information in the
knowledge base and, at the same time, inspires LLM to exploit its internal knowledge by conducting
structured reasoning and knowledge extrapolation. GIVE enables GPT3.5-turbo to achieve better
performance than GPT4 on biomedical QA benchmarks with a very sparse knowledge graph and
mitigates the hallucination issue of retrieval-based methods on sparse KG. It sheds light on the
potential of LLM to conduct divergent thinking using very limited external clues.
A
CKNOWLEDGEMENT
This effort was partially sponsored by NSF grants 2200274, 2106859 and 2312501, as well as NIH
grants U54HG012517 and U24DK097771.
R
EFERENCES
Varsha Badal, Dustin Wright, Yannis Katsis, Ho-Cheol Kim, Austin Swafford, Rob Knight, and
Chun-Nan Hsu. Challenges in the construction of knowledge bases for human microbiome-disease
associations. Microbiome, 7, 09 2019. doi: 10.1186/s40168-019-0742-2.
Yejin Bang, Samuel Cahyawijaya, Nayeon Lee, Wenliang Dai, Dan Su, Bryan Wilie, Holy Lovenia,
Ziwei Ji, Tiezheng Yu, Willy Chung, Quyet V. Do, Yan Xu, and Pascale Fung. A multitask,
multilingual, multimodal evaluation of chatgpt on reasoning, hallucination, and interactivity, 2023.
URL https://arxiv.org/abs/2302.04023.
Jonathan Berant, Vivek Srikumar, Pei-Chun Chen, Abby Vander Linden, Brittany Harding, Brad
Huang, Peter Clark, and Christopher D. Manning. Modeling biological processes for reading
comprehension. In Alessandro Moschitti, Bo Pang, and Walter Daelemans (eds.), Proceedings
of the 2014 Conference on Empirical Methods in Natural Language Processing (EMNLP), pp.
1499–1510, Doha, Qatar, October 2014. Association for Computational Linguistics. doi: 10.3115/
v1/D14-1159. URL https://aclanthology.org/D14-1159.
Tom B. Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared Kaplan, Prafulla Dhariwal,
Arvind Neelakantan, Pranav Shyam, Girish Sastry, Amanda Askell, Sandhini Agarwal, Ariel
Herbert-Voss, Gretchen Krueger, Tom Henighan, Rewon Child, Aditya Ramesh, Daniel M. Ziegler,
Jeffrey Wu, Clemens Winter, Christopher Hesse, Mark Chen, Eric Sigler, Mateusz Litwin, Scott
Gray, Benjamin Chess, Jack Clark, Christopher Berner, Sam McCandlish, Alec Radford, Ilya
Sutskever, and Dario Amodei. Language models are few-shot learners, 2020. URL https:
//arxiv.org/abs/2005.14165.
Hengxing Cai, Xiaochen Cai, Junhan Chang, Sihang Li, Lin Yao, Changxin Wang, Zhifeng Gao,
Hongshuai Wang, Yongge Li, Mujie Lin, Shuwen Yang, Jiankun Wang, Mingjun Xu, Jin Huang,
Fang Xi, Jiaxi Zhuang, Yuqi Yin, Yaqi Li, Changhong Chen, Zheng Cheng, Zifeng Zhao, Linfeng
Zhang, and Guolin Ke. Sciassess: Benchmarking llm proficiency in scientific literature analysis,
2024. URL https://arxiv.org/abs/2403.01976.
Qixin Deng, Qikai Yang, Ruibin Yuan, Yipeng Huang, Yi Wang, Xubo Liu, Zeyue Tian, Jiahao
Pan, Ge Zhang, Hanfeng Lin, Yizhi Li, Yinghao Ma, Jie Fu, Chenghua Lin, Emmanouil Benetos,
Wenwu Wang, Guangyu Xia, Wei Xue, and Yike Guo. Composerx: Multi-agent symbolic music
composition with llms, 2024. URL https://arxiv.org/abs/2404.18081.
Xiangjue Dong, Yibo Wang, Philip S. Yu, and James Caverlee. Probing explicit and implicit gender
bias through llm conditional text generation, 2023. URL https://arxiv.org/abs/2311.
00306.
Felix J. Dorfner, Amin Dada, Felix Busch, Marcus R. Makowski, Tianyu Han, Daniel Truhn,
Jens Kleesiek, Madhumita Sushil, Jacqueline Lammert, Lisa C. Adams, and Keno K. Bressem.
Biomedical large languages models seem not to be superior to generalist models on unseen medical
data, 2024. URL https://arxiv.org/abs/2408.13833.
11

Achiam et al. Gpt-4 technical report, 2024a. URL https://arxiv.org/abs/2303.08774.
Brown et al. Language models are few-shot learners. In H. Larochelle, M. Ran-
zato, R. Hadsell, M.F. Balcan, and H. Lin (eds.), Advances in Neural Infor-
mation Processing Systems, volume 33, pp. 1877–1901. Curran Associates, Inc.,
2020. URL https://proceedings.neurips.cc/paper_files/paper/2020/
file/1457c0d6bfcb4967418bfb8ac142f64a-Paper.pdf.
Chowdhery et al. Palm: Scaling language modeling with pathways, 2022. URL https://arxiv.
org/abs/2204.02311.
Dubey et al. The llama 3 herd of models, 2024b. URL https://arxiv.org/abs/2407.
21783.
Yingqiang Ge, Wenyue Hua, Kai Mei, jianchao ji, Juntao Tan, Shuyuan Xu, Zelong Li, and
Yongfeng Zhang. Openagi: When llm meets domain experts. In A. Oh, T. Naumann,
A. Globerson, K. Saenko, M. Hardt, and S. Levine (eds.), Advances in Neural Infor-
mation Processing Systems, volume 36, pp. 5539–5568. Curran Associates, Inc., 2023.
URL https://proceedings.neurips.cc/paper_files/paper/2023/file/
1190733f217404edc8a7f4e15a57f301-Paper-Datasets_and_Benchmarks.
pdf.
Bowen Jiang, Yangxinyu Xie, Zhuoqun Hao, Xiaomeng Wang, Tanwi Mallick, Weijie J. Su, Camillo J.
Taylor, and Dan Roth. A peek into token bias: Large language models are not yet genuine reasoners,
2024. URL https://arxiv.org/abs/2406.11050.
Qiao Jin, Bhuwan Dhingra, Zhengping Liu, William Cohen, and Xinghua Lu. Pubmedqa: A dataset
for biomedical research question answering. In Proceedings of the 2019 Conference on Empirical
Methods in Natural Language Processing and the 9th International Joint Conference on Natural
Language Processing (EMNLP-IJCNLP), pp. 2567–2577, 2019.
Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi
Chen, and Wen-tau Yih. Dense passage retrieval for open-domain question answering. In Bonnie
Webber, Trevor Cohn, Yulan He, and Yang Liu (eds.), Proceedings of the 2020 Conference on
Empirical Methods in Natural Language Processing (EMNLP), pp. 6769–6781, Online, November
2020. Association for Computational Linguistics. doi: 10.18653/v1/2020.emnlp-main.550. URL
https://aclanthology.org/2020.emnlp-main.550.
Anastasia Krithara, Anastasios Nentidis, Konstantinos Bougiatiotis, and Georgios Paliouras. Bioasq-
qa: A manually curated corpus for biomedical question answering. Scientific Data, 10:170, 2023.
URL https://doi.org/10.1038/s41597-023-02068-4.
Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal,
Heinrich Küttler, Mike Lewis, Wen tau Yih, Tim Rocktäschel, Sebastian Riedel, and Douwe Kiela.
Retrieval-augmented generation for knowledge-intensive nlp tasks, 2021.
Da Li, Boqing Zhu, Sen Yang, Kele Xu, Ming Yi, Yukai He, and Huaimin Wang. Multi-task
pre-training language model for semantic network completion. ACM Trans. Asian Low-Resour.
Lang. Inf. Process., 22(11), nov 2023. ISSN 2375-4699. doi: 10.1145/3627704. URL https:
//doi.org/10.1145/3627704.
Mingyu Derek Ma, Xiaoxuan Wang, Yijia Xiao, Anthony Cuturrufo, Vijay S Nori, Eran Halperin, and
Wei Wang. Memorize and rank: Elevating large language models for clinical diagnosis prediction,
October 2024a.
Mingyu Derek Ma, Chenchen Ye, Yu Yan, Xiaoxuan Wang, Peipei Ping, Timothy Chang, and Wei
Wang. Clibench: A multifaceted and multigranular evaluation of large language models for clinical
decision making. June 2024b. URL https://arxiv.org/abs/2406.09923.
Costas Mavromatis and George Karypis. Gnn-rag: Graph neural retrieval for large language model
reasoning, 2024. URL https://arxiv.org/abs/2405.20139.
12

Long Ouyang, Jeff Wu, Xu Jiang, Diogo Almeida, Carroll L. Wainwright, Pamela Mishkin, Chong
Zhang, Sandhini Agarwal, Katarina Slama, Alex Ray, John Schulman, Jacob Hilton, Fraser Kelton,
Luke Miller, Maddie Simens, Amanda Askell, Peter Welinder, Paul Christiano, Jan Leike, and
Ryan Lowe. Training language models to follow instructions with human feedback, 2022. URL
https://arxiv.org/abs/2203.02155.
Colin Raffel, Noam Shazeer, Adam Roberts, Katherine Lee, Sharan Narang, Michael Matena,
Yanqi Zhou, Wei Li, and Peter J. Liu. Exploring the limits of transfer learning with a unified
text-to-text transformer. Journal of Machine Learning Research, 21(140):1–67, 2020. URL
http://jmlr.org/papers/v21/20-074.html.
Apoorv Saxena, Aditay Tripathi, and Partha Talukdar. Improving multi-hop question answering
over knowledge graphs using knowledge base embeddings. In Dan Jurafsky, Joyce Chai, Natalie
Schluter, and Joel Tetreault (eds.), Proceedings of the 58th Annual Meeting of the Association for
Computational Linguistics, pp. 4498–4507, Online, July 2020. Association for Computational
Linguistics. doi: 10.18653/v1/2020.acl-main.412. URL https://aclanthology.org/
2020.acl-main.412.
Robyn Speer, Joshua Chin, and Catherine Havasi. Conceptnet 5.5: An open multilingual graph of
general knowledge, 2018. URL https://arxiv.org/abs/1612.03975.
Jiashuo Sun, Chengjin Xu, Lumingyuan Tang, Saizhuo Wang, Chen Lin, Yeyun Gong, Lionel M. Ni,
Heung-Yeung Shum, and Jian Guo. Think-on-graph: Deep and responsible reasoning of large
language model on knowledge graph, 2024.
Alon Talmor, Jonathan Herzig, Nicholas Lourie, and Jonathan Berant. Commonsenseqa: A question
answering challenge targeting commonsense knowledge, 2019. URL https://arxiv.org/
abs/1811.00937.
Wim J.C. Verhagen, Pablo Bermell-Garcia, Reinier E.C. van Dijk, and Richard Curran. A critical
review of knowledge-based engineering: An identification of research challenges. Advanced Engi-
neering Informatics, 26(1):5–15, 2012. ISSN 1474-0346. doi: https://doi.org/10.1016/j.aei.
2011.06.004. URL https://www.sciencedirect.com/science/article/pii/
S147403461100036X. Network and Supply Chain System Integration for Mass Customization
and Sustainable Behavior.
Xuezhi Wang, Jason Wei, Dale Schuurmans, Quoc Le, Ed Chi, Sharan Narang, Aakanksha Chowdh-
ery, and Denny Zhou. Self-consistency improves chain of thought reasoning in language models,
2023. URL https://arxiv.org/abs/2203.11171.
Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le,
and Denny Zhou. Chain-of-thought prompting elicits reasoning in large language models, 2023.
Yangxinyu Xie, Bowen Jiang, Tanwi Mallick, Joshua David Bergerson, John K. Hutchison, Duane R.
Verner, Jordan Branham, M. Ross Alexander, Robert B. Ross, Yan Feng, Leslie-Anne Levy, Weijie
Su, and Camillo J. Taylor. Wildfiregpt: Tailored large language model for wildfire analysis, 2024.
URL https://arxiv.org/abs/2402.07877.
Yao Xu, Shizhu He, Jiabei Chen, Zihao Wang, Yangqiu Song, Hanghang Tong, Kang Liu, and Jun
Zhao. Generate-on-graph: Treat llm as both agent and kg in incomplete knowledge graph question
answering, 2024. URL https://arxiv.org/abs/2404.14741.
Daoguang Zan, Sirui Wang, Hongzhi Zhang, Kun Zhou, Wei Wu, Wayne Xin Zhao, Bingchao Wu,
Bei Guan, and Yongji Wang. Complex question answering over incomplete knowledge graph as
n-ary link prediction. In 2022 International Joint Conference on Neural Networks (IJCNN), pp.
1–8, 2022. doi: 10.1109/IJCNN55064.2022.9892700.
Yubo Zhang, Shudi Hou, Mingyu Derek Ma, Wei Wang, Muhao Chen, and Jieyu Zhao. Climb: A
benchmark of clinical bias in large language models, 2024. URL https://arxiv.org/abs/
2407.05250.
Ruizhe Zhong, Xingbo Du, Shixiong Kai, Zhentao Tang, Siyuan Xu, Hui-Ling Zhen, Jianye Hao,
Qiang Xu, Mingxuan Yuan, and Junchi Yan. Llm4eda: Emerging progress in large language models
for electronic design automation, 2023. URL https://arxiv.org/abs/2401.12224.
13

A A GIVE
LGORITHM FOR
We summarize the comprehensive procedure of GIVE and present its detailed algorithm in Algorithm
1
Algorithm 1: GIVE
Input: Entity groups N ; Possible relations between two entity groups R ; Knowledge Graph G
x x
˜
Output: T (G), the approximated gold knowledge set that helps to solve query x
x
˜
T a(G) ← ∅
1
x
˜
T c(G) ← ∅
2
x
˜
T e(G) ← ∅
3
x
for all queried entity e i and their corresponding relevant concepts y j ∈ N i do
4
x x x
// build inner-group connections
(e i , y j ) → LLM → (e i , r ij , y j )
5 x , x x x x
˜ ˜
T a(G) ← T a(G) ∪ {(e i , r ij , y j )}
6
x x x x x
for (N i , N j ) pairs in N × N do
7 x x x x
// build inter-group connections
˜
retrieve all triplets T e(G ij) ∈ E connecting any node in N i and any node in N j
8 x G x x
˜ ˜ ˜
T e(G) = T e(G) ∪ T e(G ij)
9
x x x
R ij ← set of relation types in T ˜ e(G ij) R ij ← R ij ∪ R
10 G x x G x
for all triplets (n i , r ij , n j ) in (N i × R ij × N j ) do
11
x x x x x x
(n i , r ij , n j ) → LLM → yes,no or maybe
12
x x x
if yes then
13
˜ ˜
T a(G) = T a(G) ∪ (n i , r ij , n j )
14
x x x x x
if no then
15
˜ ˜
T c(G) = T c(G) ∪ (n i , not r ij , n j )
16
x x x x x
˜ ˜ ˜
return T a(G), T c(G), T e(G)
17
x x x
B A A
DDITIONAL BLATION STUDIES
In addition to Section 4.4, we conduct more detailed ablation studies for GIVE to study the robustness
of the proposed method and other factors that may influence its performance. All experiments in this
Section are based on 50 randomly generated examples for each dataset, whereas in Section 4.4, we
study the influence of different numbers of entities per group on the full dataset.
B.1 N
UMBER OF SEEDED EXAMPLES
To better understand how difficult it is for LLMs to get the generalized ability to adopt the knowledge
generated by GIVE to build the structured reasoning chain, we study the performance of GIVE by
providing different number of examples in the prompt. For yes-no datasets PubmedQA (Jin et al.,
2019) and BioASQ (Krithara et al., 2023), we randomly choose k of {0, 1, 2, 3, 4, 5} examples.
For multiple-choice datasets Processbank (Berant et al., 2014) and CSQA (Talmor et al., 2019), we
choose k of {0, 1, 3, 5, 7, 10}. The results are presented in Figure 5.
We observe that although the performance of GIVE increases as we give more seeded examples
in the prompt, the only one large performance upgrade happens when we increase the number of
examples from 0 to 1. This implies that GIVE is a generalizable framework for the LLM to easily
adopt. The high performance of GIVE does not rely on large number of examples, but stems from the
high quality of the synthetic data it generates.
B.2 D
IFFERENT WAYS OF PROMPTING
14

Figure 5: Sensitivity analysis of GIVE on different number of seeded examples.
We perform additional experiments in this sub-
Table 4: Performance of GIVE using different
section to study how different prompting strate-
prompting methods on 50 randomly chosen ex-
gies influence the performance of GIVE. We
amples for each dataset. We highlight in green
verbalize the retrieved knowledge and prompt
the better-performed prompting method and the
them in the form of triplets and text, and the
performance difference.
results are presented in in Table 4. We notice
that in most cases, prompting the knowledge in
GPT3.5-turbo
triplets yields to higher accuracy than prompting # Prompting Method / dataset
PubmedQA BioASQ Processbank CSQA
knowledge in text. This is because the struc-
GIVE
a
ture of triplets naturally provides an easier way
1 Triplet prompt 32 86 76 74
2 Text prompt 46 86 74 62
for the LLM to connect the related entities and
GIVE
a+c
build faithful logical chain to solve the question.
1 Triplet prompt 56 86 74 76
However, for text-based information, additional
2 Text prompt 54 84 74 70
analyzing step is needed to understand the text GIVE
a+c+e
before it links the useful information together, 1 Triplet prompt 52 88 70 76
2 Text prompt 54 84 72 68
which is a difficult task for reasoning-intensive
queries where the volumn of additional knowledge is high.
B.3 E
NCODING MODEL SIZE
In Section 3.2, we employ SentenceTransformer as encoder model to measure the text similarities for
entity group construction. We investigate the impacts of using different sizes on the performance
of GIVE, and demonstrate the results in Table 5. We see that although larger size encoder models
achieve better sentence embedding or performance semantic search performance, small to middle
size encoders tend to perform more consistently on all datasets. For the best-performing GIVE ,
a+c+e
the 80M encoder (all-MiniLM-L6-v2) achieves 8% higher accuracy than the 420M one (all-mpnet-
base-v2). The results show that larger size encoders do not necessarily better measure text similarity
between specific domain terms. On the other hand, the performance of GIVE does not rely on the
size of the models employed, which enhances the efficiency of GIVE.
15


| 32
46 | 86
86 | 76
74 |
| --- | --- | --- |

| 56
54 | 86
84 | 74
74 |
| --- | --- | --- |

| 52
54 | 88
84 | 70
72 |
| --- | --- | --- |
Table 5: Performance of GIVE using GPT3.5-turbo and encoding SentenceTransformers of different
sizes to search for relevant entities to build entity group (Section 3.2). Results are based on 50
randomly generated samples for each dataset. We highlight the results from the best performing
model in green.
GPT3.5-turbo
# Encoding model(size) / dataset
PubmedQA BioASQ Processbank CSQA
GIVE
a
1 paraphrase-albert-small-v2(43M) 44 84 74 68
2 all-MiniLM-L6-v2(80M) 32 86 76 74
3 all-MiniLM-L12-v2(120M) 24 80 62 72
4 all-mpnet-base-v2(420M) 38 88 66 64
GIVE
a+c
1 paraphrase-albert-small-v2(43M) 54 82 76 70
2 all-MiniLM-L6-v2(80M) 56 86 74 76
3 all-MiniLM-L12-v2(120M) 52 82 62 70
4 all-mpnet-base-v2(420M) 52 86 62 64
GIVE
a+c+e
1 paraphrase-albert-small-v2(43M) 52 84 76 72
2 all-MiniLM-L6-v2(80M) 52 88 70 76
3 all-MiniLM-L12-v2(120M) 54 82 62 70
4 all-mpnet-base-v2(420M) 52 88 60 64
C D GIVE
ETAILED ANALYSIS OF
C.1 W " "?
HAT MAKES GOOD INSPIRATIONS
We noticed that the accuracy improvement of GIVE alternates across different QA datasets, to
carefully examine what makes the different capabilities of GIVE in boosting LLM’s performance, we
randomly sample 50 questions from PubemdQA (Jin et al., 2019), BioASQ (Krithara et al., 2023),
ProcessBank (Berant et al., 2014) and CSQA (Talmor et al., 2019). Specifically, From Table 1 and
Table 3, we found that when vanilla LLM does not have enough internal knowledge (I/O prompting
gets poor performance), the accuracy improvement achieved by GIVE has the trend of BioASQ >
PubmedQA > Processbank > CSQA. The different performance of GIVE stems from the ratio
of expert KG knowledge in the whole retrieved knowledge set. To better see this, we define
∣T˜(G)∣
˜ ˜
expert ratio for a query x to be , where T
(G)e
, T
(G)a
are the set of expert
x x
∣T˜(G)∣+∣T˜(G)∣+∣T˜(G)∣
KG knowledge, affirmative knowledge and counter-factual knowledge we retrieved from Section
3.4.3. We then calculate the average expert ratio of 50 randomly chosen samples for each dataset and
demonstrate the relationship between the average expert ratio and the best accuracy gain of GIVE
compared to I/O prompting in Figure 6.
There is a positive correlation between the performance of GIVE and the ratio of expert KG
knowledge. The reason behind this is with the larger number of seeded expert triplets, GIVE would
have more concrete candidate relations and related entities for the LLM to conduct divergent thinking
in the proposed "inspiration" process. The quality of the synthetic knowledge depends on the number
of seeded expert KG knowledge provided. In the case that there are only few KG knowledge (for
CSQA on the 50%-triplet Conceptnet), most retrieved knowledge are based only on LLM’s internal
knowledge to decide openly what the relationship is between two concepts. When the give KG is
rich in information, the ground truth triplets provide a high-quality "supervise" for the "inspiration"
process to "hint" the model what kind of relationship may exist between the entities. To further
backup this statement, we divide these 50 randomly sampled questions from PubemdQA, BioASQ
and Processbank into sub-groups according to their expert ratio, and we calculate the average accuracy
16

Figure 6: Best accuracy gain of GIVE and expert ratios for each dataset on 50 randomly chosen
questions. For CSQA, we report the results using 50%-triplet version of ConceptNet.
Figure 7: Accuracy achieved by GIVE for questions with different expert ratio (KG knowledge
∣T˜(G)∣
˜ ˜
ratio), calculated by , where T
(G)e
, T
(G)a
are the set of expert KG knowledge,
x x
∣T˜(G)∣+∣T˜(G)∣+∣T˜(G)∣
affirmative knowledge and counter-factual knowledge we retrieved from Section 3.4.3.
17

Figure 8: Average number of entity groups (left), average number of candidate relations between two
groups (middle) and average percentage of questions that requires intermediate entity group (right)
for each dataset included in Section 4.2 and 4.3 for 5 runs. For CSQA, we report the results on 50%
triplets version of ConceptNet.
for each sub-group. The results are demonstrated in Figure 7. We get the uniform conclusion that on
every dataset that expert guidance (KG knowledge) is available, GIVE gets very high performance
on the questions with high expert ratio. On the questions that nearly purely relies on the internal
knowledge of LLM, the performance of GIVE is much degraded. It turns out that neither external
knowledge or internal knowledge itself is able to solve knowledge-intensive tasks, efforts must
be made to fill this gap, and GIVE is designed for this.
C.2 E GIVE
FFICIENCY OF
In Section 5 we discussed the efficiency of GIVE and concluded that the key factors that influence the
number of LLM calls required by GIVE is the number of entity groups detected for the query and the
number of candidate relations between each pair of entity groups. To conduct a more detailed study
on the scale of them, we run GIVE 5 times on 50 randomly selected questions for each of the datasets
we included in Section 4.2 and 4.3, and we report the average number of entity groups, average
number of candidate relations to connect two entity groups, and average percentage of questions
that requires intermediate entity groups (3.4.2) for multi-step reasoning. The results are presented in
Figure 8.
We observe that on average, GIVE requires around 3 entities groups for each question in the
Biomedical datasets (PubmedQA, BioASQ, Processbank), between each datasets, there could be
1 to 6 candidate relations. For commonsenseQA, 4 entity groups on average are detected because
the dataset has 5 candidate options, between each pair of entity groups, only 1 candidate relation is
detected in general. We also notice that 60% of the questions in PubMedQA requires intermediate
group. That is the reason why PubmedQA tends to need more entity groups than BioASQ as a
"yes-no" QA dataset. This implies one of the potential method to improve efficiency of GIVE is to
disable intermediate group detection. On the other hand, we can use the LLM to prune the candidate
connections in batches, which means in Section 3.4.3, instead of asking LLM "yes" or "no" for each
potential connection, we can prompt the LLM with a set k of relations and let it select out which ones
are true of false, which will devide the total number of LLM calls by the factor of k for GIVE.
C.3 D
ETAILED COMPARISON WITH EXISTING RETRIEVAL METHODS
In addition to Table 1 and 2, we conduct detailed performance comparison against text-based retrieval
method RAG (Lewis et al., 2021) and KG-LLM retrieval method (Sun et al., 2024), we calculate the
portions of questions answered correctly by each method and present the statistics in Figure 9 and
Figure 10.
We observe that on three of the four datasets (BioASQ, Processbank, CommonsenseQA), we included
in our experiments, most of the questions answered correctly by ToG or RAG is also answered
only ToG/RAG correct
correctly by GIVE. We see this by calculating the ratio . For example, its
+
only ToG/RAG correct both correct
18

Figure 9: The proportions of questions answered correctly by GIVE and ToG, on PubmedQA,
BioASQ, Processbank and CommonsenseQA
11% on CommonsenseQA for ToG, meaning that 89% of the questions it answered correctly is also
answered correctly by GIVE. On PubmedQA, this ratio is large because RAG and ToG both get
very poor performance, which means very few questions in this dataset can be directly answered by
the knowledge contained in the sparse KG, this further highlights the importance of the proposed
"Inspiration" process to combine internal knowledge and external knowledge to solve challenging
scientific questions.
D P
ROMPTS AND EXAMPLE RESPONSES
D.1
IO PROMPT
You are a helpful assistant that answers a given question about medical knowledge with yes, no or
maybe, based on your own knowledge.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Output: no
19

Figure 10: The proportions of questions answered correctly by GIVE and RAG, on PubmedQA,
BioASQ, Processbank and CommonsenseQA
D.2
COT PROMPT
You are a helpful assistant that answers a given question about medical knowledge with yes, no or
maybe, based on your own knowledge.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Let’s think step by step.
Output: maybe
D.3
RAG PROMPT
For RAG, we provide both the correct textual knowledge and reasoning chain for each of the k-shot
examples.
You are a helpful assistant that answers a given question about medical knowledge with yes, no or
maybe, based on the retrieved textual knowledge "entity relation entity" from an expert knowledge
graph.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Knowledge: [Textual knowledge]
Output: no
20

D.4
TOG PROMPT
We follow the official implementation of ToG (Sun et al., 2024) at official ToG GitHub and use the
default prompts. We replace the k-shot examples to be examples randomly selected for each dataset,
and we provide the correct reasoning chain. Overall, we use exact the same k-shot examples for ToG
and our method to guarantee fair comparison.
Exemplar prompt for retrieving top entities:
Please retrieve the top entities (separated by semicolon) that contribute to the question.
[EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Output: [Entities retrieved]
Exemplar prompt for pruning relations:
Please retrieve 1 relation that contributes to the question the most from the given relation list. The
answer must be one of the given relations.
[EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Relations: [Relations list]
Output: [Relationship selected]
Exemplar prompt for pruning entities:
Please score the entities’ contribution to the question on a scale from 0 to 1 (the sum of the scores of
all entities is 1). [EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Relation: [Relationship selected]
Entities: [Entities list]
Output: [Entity selected]
Exemplar prompt for evaluating knowledge sufficiency:
Given a question and the associated retrieved knowledge graph triplets (entity, relation, entity), you
are asked to answer whether it’s sufficient for you to answer the question with these triplets and your
knowledge (yes or no).
[EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Knowledge triplets: [currently retrieved knowledge triplets]
Output: [yes/no]
Exemplar prompt for ToG answering the question:
Given a question and the associated retrieved knowledge graph triplets (entity, relation, entity), you
are asked to answer the question with these triplets and your knowledge.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
Knowledge triplets: [retrieved knowledge triplets]
Output: maybe
D.5
GIVE PROMPT
Exemplar prompt for extracting and ranking the entities in the question:
21

Please retrieve the top entities that contribute to the question. Answer only the top entities, separated
by comma.
[EXAMPLES]
Question: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma
severity?
Output: [’traumatic aortic injury’, ’anatomy’, ’aortic arch’, ’aortic trauma severity’]
Exemplar prompt for extracting the relationships in the question:
Please retrieve the relationships that connect the given entities in the question.
[EXAMPLES]
Question: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma
severity?
Entities: traumatic aortic injury, anatomy, aortic arch, aortic trauma severity
Output: [’influence’]
Exemplar prompt for generating relationships between two given entities:
You are a helpful assistant that answers a short relationship in a few words between two given
biomedical entities.
[EXAMPLES]
Entities: traumatic aortic injury, injury and poisoning
Output: "is a"
Exemplar prompt for determining if relations exists between cross group entities:
You are a helpful assistant that answers yes, no or maybe depending on the correctness of the given
statement.
Injury or poisoning is the result of organism function. Is it true?
Output: "No"
Exemplar prompt for selecting optimal 2-hop path for intermediate entity group construction:
You are a helpful assistant that selects one from the given knowledge facts (entity, relation, entity,
relation, entity), that is most important to the given question.
Knowledge Facts:
(steroid, affects, organ or tissue function, affects, invertebrate),
(steroid, affects, experimental model of disease, manifestation of, injury or poisoning),
(anatomical abnormality, manifestation of, organism function, affects, clinical attribute)...
Question to answer: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic
trauma severity?
Output: (anatomical abnormality, manifestation of, organism function, affects, clinical at-
tribute)
Exemplar prompt for generating GIVE :
a
You are a helpful assistant that answers a given question about medical knowledge with yes, no or
maybe, based on the retrieved knowledge triplets (entity, relation, entity) from your own knowledge.
The return must be one of yes, no or maybe.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
[AFFIRMATIVE KNOWLEDGE TRIPLETS]
eg: (’anatomical abnormality’, ’affects’, ’organism function’), (’injury or poisoning’, ’affects’,
’organism function’), (’anatomy’, ’part of’, ’aortic arch’), (’injury or poisoning’, ’affects’, ’organ or
tissue function’), (’aortic arch’, ’location of’, ’injury or poisoning’)...
Output: maybe (GIVE )
a
22

Exemplar prompt for generating GIVE :
a + c
You are a helpful assistant that answers a given question about medical knowledge with yes, no or
maybe, based on the retrieved knowledge triplets (entity, relation, entity) from your own knowledge.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
[AFFIRMATIVE KNOWLEDGE TRIPLETS]
eg: (’anatomical abnormality’, ’affects’, ’organism function’), (’injury or poisoning’, ’affects’,
’organism function’), (’anatomy’, ’part of’, ’aortic arch’), (’injury or poisoning’, ’affects’, ’organ or
tissue function’), (’aortic arch’, ’location of’, ’injury or poisoning’)...
A: maybe (GIVE )
a
Additional knowledge triplets: [COUNTER-FACTUAL KNOWLEDGE TRIPLETS]
eg: (’organism’, ’not result of’, ’aortic trauma severity’), (’injury or poisoning’, ’not complicates’,
’anatomical structure’), (’aortic arch’, ’not influence’, ’injury or poisoning’)...
Output: yes (GIVE )
a+c
Exemplar prompt for generating GIVE :
a + c + e
You are a helpful assistant that answers a given question about medical knowledge with yes, no or
maybe, based on the retrieved knowledge triplets (entity, relation, entity) from your own knowledge,
and the knowledge triplets from an expert knowledge base. The return must be one of yes, no or
maybe.
[k-shot EXAMPLES]
Q: Traumatic aortic injury: does the anatomy of the aortic arch influence aortic trauma severity?
[AFFIRMATIVE KNOWLEDGE TRIPLETS]
eg: (’anatomical abnormality’, ’affects’, ’organism function’), (’injury or poisoning’, ’affects’,
’organism function’), (’anatomy’, ’part of’, ’aortic arch’), (’injury or poisoning’, ’affects’, ’organ or
tissue function’), (’aortic arch’, ’location of’, ’injury or poisoning’)...
A: maybe (GIVE )
a
Additional knowledge triplets: [COUNTER-FACTUAL TRIPLETS]
eg: (’organism’, ’not result of’, ’aortic trauma severity’), (’injury or poisoning’, ’not complicates’,
’anatomical structure’), (’aortic arch’, ’not influence’, ’injury or poisoning’)...
A: yes (GIVE )
a+c
Additional knowledge triplets retrieved from expert knowledge base: [EXPERT KG KNOWL-
EDGE TRIPLETS]
eg: (’injury or poisoning’, ’result of’, ’anatomical abnormality’), (’steroid’, ’causes’, ’injury or
poisoning’), (’injury or poisoning’, ’complicates’, ’anatomical abnormality’), (’anatomical abnor-
mality’, ’result of’, ’injury or poisoning’)...
Output: yes (GIVE )
a+c+e
23

