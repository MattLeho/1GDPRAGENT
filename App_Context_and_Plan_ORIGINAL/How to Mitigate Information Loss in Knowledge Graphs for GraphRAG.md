# Converted from How to Mitigate Information Loss in Knowledge Graphs for GraphRAG.pdf

How to Mitigate Information Loss in Knowledge Graphs for GraphRAG:
Leveraging Triple Context Restoration and Query-Driven Feedback
1 1 2 1
Manzong Huang , Chenyang Bu , Yi He , Xindong Wu
1
Key Laboratory of Knowledge Engineering with Big Data (Hefei University of Technology), Ministry
of Education, China
2
School of Data Science, William & Mary, Williamsburg, VA, USA
manzonghuang@mail.hfut.edu.cn {chenyangbu, xwu}@hfut.edu.cn yihe@wm.edu
Abstract
What is Einstein's most famous
Theory of Missing
Albert Einstein was a relativity Extraction achievement?
German-born theoretical Information sparsity occurs
Knowledge Graph (KG)-augmented Large Lan- best
physicist who is best Text-to- developed when incomplete extraction
known for
known for developing the Graph
guage Models (LLMs) have recently propelled results in a failure to meet query
Albert
theory of relativity. , …,
Einstein requirements.
significant advances in complex reasoning tasks, He received the 1921
Nobel Prize in Physics for received discovered
What did Einstein win the Nobel
thanks to their broad domain knowledge and con-
his services to theoretical
Prize for, theory of relativity or
1921 Nobel Photoelectric
physics, and especially for
textual awareness. Unfortunately, current meth- Prize in Physics effect photoelectric effect?
his discovery of the law of
Dependencies missing due to
the photoelectric effect.
ods often assume KGs to be complete, which is
Dependencies
context loss.
missing
impractical given the inherent limitations of KG
construction and the potential loss of contextual Figure 1: Illustration of two main factors of information loss in KGs:
cues when converting unstructured text into entity- information sparsity and context loss. These issues hinder LLMs
from accurately answering questions based on KGs.
relation triples. In response, this paper proposes the
Triple Context Restoration and Query-driven Feed-
back (TCR-QF) framework, which reconstructs the
leading to missing or incomplete relations [Zhu et al., 2024;
textual context underlying each triple to mitigate
Zhong et al., 2024]. Such missing information in KGs can
information loss, while dynamically refining the
significantly degrade the LLM reasoning capabilities.
KG structure by iteratively incorporating query-
To wit, Figure 1 illustrates two primary sources of infor-
relevant missing knowledge. Experiments on five
mation loss. First, information sparsity arises when in-
benchmark question-answering datasets substanti-
formation extraction falls short, omitting potentially impor-
ate the effectiveness of TCR-QF in KG and LLM
tant triples and thus failing to provide sufficient coverage
integration, where it achieves a 29.1% improve-
for specific queries [Biswas et al., 2024; Xu et al., 2024b;
ment in Exact Match and a 15.5% improvement in
Li et al., 2023; Zhang and Soh, 2024; Chen et al., 2024a;
F1 over its state-of-the-art GraphRAG competitors.
Sun et al., 2024; Cohen et al., 2023]. This sparsity can be
exacerbated by data noise, long-tail entities, and complex
1 Introduction
relationships, where extraction algorithms often falter. Sec-
Large Language Models (LLMs) augmented with Knowledge ond, context loss occurs when transforming rich yet unstruc-
Graphs (KGs) have achieved remarkable successes across di- tured text into discrete triples, sacrificing crucial semantic
verse domains, from social sciences to biomedicine [Pan et nuances and relational dependencies [Trisedya et al., 2019;
al., 2024; Peng et al., 2024; Yang et al., 2024; Soman et al., Paulheim, 2017; Xu et al., 2024a]. While prior studies at-
2024]. By harmonizing the structured information in KGs tempt to mitigate this issue by refining graph structures or
and the sophisticated language understanding and processing retrieval algorithms [Liang et al., 2024; Chen et al., 2024b;
capabilities of LLMs, such hybrid systems enable more accu- Panda et al., 2024; Munikoti et al., 2023; Cohen et al., 2023],
rate and context-aware reasoning for complex tasks. their subgraphs still lack the broader contextual information
Despite these advances, the performance of current KG– that is vital for robust reasoning, resulting in suboptimal per-
LLM integration methods is often hindered by the underly- formance in downstream tasks.
ing assumption that the KG is complete. Typical integra- To address these challenges, we propose the Triple
tion strategy involves retrieving relational data from a con- Context Restoration and Question-driven Feedback (TCR-
structed KG and feed it into LLMs via prompt augmenta- QF) framework, which aims to restore the missing contextual
tion [Peng et al., 2024; Sun et al., 2023; Edge et al., 2024], information and dynamically enrich the KG during the rea-
assuming that critical entities and relationships relevant to the soning process. Specifically, our TCR-QF approach presents
query are already captured within the KG. In practice, how- a triple context restoration component that retrieves the orig-
ever, KG construction itself is beset by inherent constraints, inal text passages associated with each triple, thereby recap-
where vital contextual information can be discarded in the turing the semantic details often lost during KG construc-
process of converting unstructured text into structured triples, tion. We further enhance KG coverage through a query-
5202
naJ
62
]IA.sc[
1v87351.1052:viXra


| What is Einstein's most famous
achievement? |
| --- |
| Information sparsity occurs
when incomplete extraction
results in a failure to meet query
requirements. |

| dev | elope | d best |
| --- | --- | --- |

| What did Einstein win the Nobel
Prize for, theory of relativity or
photoelectric effect? |
| --- |
| Dependencies missing due to
context loss. |
driven feedback mechanism, which iteratively identifies miss- However, the lack of essential data negatively impacts the
ing information relevant to the query and enriches the KG inference results of LLMs. To address this, efforts have been
accordingly. These two components together form a syner- made to enhance KG comprehensiveness through refined in-
gistic cycle in which contextual fidelity and KG complete- dexing methods and innovative graph structures for retriev-
ness are continuously reinforced, resulting in more accurate ing both triples and texts [Chen et al., 2024b; Munikoti et al.,
and context-aware responses from the LLM. Empirical study 2023; Liang et al., 2024; Cohen et al., 2023], as well as us-
on five benchmark question-answering datasets substantiates ing LLMs to improve automated KG construction [Zhang and
that TCR-QF significantly outperforms the state-of-the-art Soh, 2024; Xu et al., 2024b; Li et al., 2023]. These methods
GraphRAG methods in both response accuracy and complete- may retrieve texts related to the query without fully meeting
ness, demonstrating its effectiveness. its requirements. Additionally, the retrieved subgraphs can
result in the loss of crucial information due to the absence
Specific Contributions of this paper are as follows:
of contextual data within triples, which is essential for main-
1) We provide a systematic analysis of the key challenges
taining semantic integrity. As a result, the constructed KG
in KG–LLM integration, highlighting the loss of con-
may lack critical information necessary for accurate reason-
textual information and incomplete information extrac-
ing, leading to suboptimal performance in downstream tasks.
tion during KG construction, both of which hinder an
The proposed TCR-QF framework addresses these limita-
advanced LLM reasoning performance.
tions by dynamically enriching the KG during the reasoning
2) We propose the TCR-QF framework, which restores the process. By restoring the original textual context of triples,
semantic context associated with triples and employs a TCR-QF recovers lost semantic information. Additionally,
query-driven feedback mechanism to iteratively enrich it employs a query-driven feedback mechanism to identify
the KG, thereby significantly enhancing the LLM rea- and fill in missing information relevant to a query, enabling
soning capabilities. the KG to continuously update. This mutual enhancement
between KG and LLM improves reasoning performance and
3) Extensive experiments on five benchmark question-
better adapts to task requirements.
answering datasets are carried out, showing that TCR-
QF achieves an average 29.1% improvement in Ex-
3 Proposed Method
act Match and a 15.5% improvement in F1 over its
GraphRAG competitors. These results validate the merit
In this section, we present the TCR-QF framework, designed
of restoring contextual information and dynamically up-
to mitigate the loss of contextual information when building
dating KGs for effective KG–LLM integration.
knowledge graphs (KGs) from unstructured text and to dy-
namically enrich these graphs during the reasoning process.
2 Related Work
As shown in Figure 2, the framework comprises four key
components: (1) Knowledge Graph Construction, which
GraphRAG has emerged as a powerful paradigm for inte-
builds a unified KG from textual sources; (2) Subgraph
grating knowledge graphs (KGs) with large language models
Retrieval, responsible for extracting task-relevant subgraphs
(LLMs) to advance complex reasoning tasks [Pan et al., 2024;
composed of potential reasoning paths; (3) Triple Context
Peng et al., 2024; Yang et al., 2024]. A widely adopted
Restoration, which traces back the original textual context
strategy involves retrieving relevant subgraphs from pre-
of each triple to recover lost semantic nuances; and (4) It-
constructed KGs to augment LLMs during inference [Ya-
erative Reasoning with Query-Driven Feedback, where
sunaga et al., 2021; Taunk et al., 2023], with techniques
an iterative cycle that both generates answers and identifies
such as extracting hop-k paths around topic entities [Ya-
missing knowledge, thereby refining the KG on-the-fly. To-
sunaga et al., 2021] or focusing on the shortest paths rele-
gether, these components ensure that contextual details are
vant to query entities [Delile et al., 2024]. More sophisti-
preserved and the KG remains up-to-date, ultimately enhanc-
cated methods optimize subgraph retrieval by assigning edge
ing the quality and depth of the system reasoning.
costs [He et al., 2024] or leverage LLMs themselves to gen-
The above steps establishes a synergistic cycle for two-way
erate new relations or invoke function calls [Kim et al., 2023;
knowledge enhancement, namely,
Jiang et al., 2023].
While these approaches have demonstrated effectiveness,
Forward Flow: The KG informs the LLM during answer
most remain limited by their dependence on the initial com-
generation, represented as
pleteness of the KG and often overlook the contextual infor-
mation lost during KG construction. In reality, KGs are fre- (i)
(i) ′(i)
G −→ G −→ A .
LLM
quently incomplete due to information loss during construc-
tion and the difficulties in extracting all relevant triples, es- (i)
In the i-th iteration, a subgraph is retrieved from the KG G
pecially in noisy or complex scenarios [Biswas et al., 2024;
′(i)
and enhanced through triple context restoration to form G .
Cohen et al., 2023]. These constraints can hinder the abil-
(i)
′(i)
The LLM then infers the answer A based on G .
ity of LLMs to formulate coherent and context-rich reason- LLM
ing paths. Addressing these gaps calls for a more dynamic Feedback Flow: The missing knowledge in the KG is iden-
strategy that restores missing contextual details and continu- tified and subsequently integrated back into the KG:
ously refines the KG, ensuring that the retrieved and gener-
(i)
(i+1) (i)
ated knowledge is both accurate and semantically complete. G ←− ∆K ←− A ,
LLM

Question: For what achievement was Einstein awarded the Nobel Prize in Physics?
Initial KG
Construction
TTrriippllee CCoonntteexxtt RReessttoorraattiioonn
Nobel Prize in
Physics --ggooaall--
enriched subgraph
AAnnsswweerr tthhee qquueessttiioonn wwiitthh
Subgraph
Nobel Prize in Retrieval received TTTT TTTT eeee eeee mmmm mmmm pppp pppp llllaaaa llllaaaa tttt RRRR eeee tttteeee oooo CCCC CCCC HHH PPP HHH rrr eee iiiHHH eee zzz rrr eee eee eee rrr ccc eee iiirrr eee nnn ccc eee iii eee ccc vvv PPP iii eee eee vvv hhhiii ddd eee vvvyyy ddd eeesss ttthhh dddiii ttt ccc eee hhh tttsss eee hhh,,, 111 eee……… 999 111 222 999 111,,, 111 222 999 fff 111 222 NNN ooo 111 NNN rrr ooo NNNhhh bbb ooo iii eee bbb ooosss lll eee bbb lll eee lll bbeellooww iinnffoorrmmaattiioonn.. ......
Physics TTTTeeeemmmmppppllllaaaatttteeee nnnnooooCCCC PPPrrriiizzzeee iiinnn PPPhhhyyysssiiicccsss,,, ………,,, fffooorrr hhhiiisss CCoonntteexxtt::
Germany E A in lb st e e r i t n RRRReeeettttrrrriiiieeeevvvvaaaa RRRR llll RRRR xxxx eeee tttt eeee tttt nnnn nnnn oooo dddiii ddd sssPPP iii ddd ccc sss ppp rrr iii ooo ccc iii ssshhh zzzvvv ooo cccooo eeeeee vvv ooottt rrr ooo eee vvv iiiyyynnn rrr eeeeee yyy lllrrr oooPPP eee yyy fff ooo ccc hhh fff ooo ttt ttt yyy hhh rrrfff ttt sss iii eee hhh ccc iii ttt ccc eee hhh lll eee sss aaa eee lll fff ,,,www aaa ffflll ……… eee www aaa ccc ooo www ttt ,,,fff ooo ... fff fff ooo tttooohhh fff ttt rrreee hhh ttt hhh eee hhh iii eee sss <<hh11,, rr11,, tt11>> RRRRR
received Photoelectric developed RRRR RRRR eeee eeee ttttrrrr tttt iiii rrrr eeee iiiieeee vvvv vvvv aaaa aaaa llll llll cccc aaaa rrrr TTTT tttt rrrr TTTT tttt xxxx TTTT tttt xxxx eeee tttt EEE AAA iii EEE nnnAAA lll iii bbb sss nnn ttt AAA lll eee eeebbb sss rrr ttt iii lll eee ttt ppp eee nnn bbb rrr iiieee ttt hhh ppp nnn rrr ddd ooo ttt hhh iii ddd ttt sss ooo ooo ccc iii ddd ttt sss ooo eee ooo ccc iii vvv sss ooo lll eee ccc eee eee vvv ooo rrr lll eee ccc eee eee vvv rrr ddd ttt eee ccc eee rrr rrr ddd ttt iii eee rrr ccc PPP ddd iii hhh ccc PPP eee ooo hhh fff PPP eee eee ttt ooo ooo fff fff hhh fff eee tttfff eee eee ooo ooo fff eee fff lll ccc tttfff eee eee eee ccc oooeee ttt lll ccc ttt ccc eee eee ccc ... ttt ttt lll ccc ttt rrr eee iii ... ttt ccc ccc rrriii ttt ccc rrriii ccc S < S < oo hh uu 22 rr ,, cc rr ee 22 :: ,, << tt ss 22 ee >> nntteennccee>> RRRRR
was born in effect discovered Theory of nnnn iiii cccc aaaa aaaa rrrr EEEiiinnnsssttteeeiiinnn eeeffffffeeecccttt SSoouurrccee:: <<sseenntteennccee>>
relativity ggggnnnn iiii cccc
……
discovered ggggnnnn iiii
gggg QQ::{{QQuueessttiioonn}} QQQQuueeuusseettiissoottnniioonn
Albert Photoelectric
Einstein effect
proposed
developed
Reasoning
mass–energy Question-driven
equivalence
Feedback
Theory of
relativity
--ggooaall--
included AAAAAllbblllbbbeerreeett rrrttt
Special EE EEE ii iii nn nnn sstt sss ee ttt iinn eeeiiinnn kk dd 11kk iiEE ::kk dd 11 WW ii 11 ::kk EEnn WW:: 11 WWhh ssii :: nntt WW aa hh ee hh ss tt aa ttii aa hh eenn dd tttt aa ii ii nn ddtt dd ii dd RR RReeeettttrrrriieeiieevvvvaaaallll IIddeennttiiffyy tthhee mmiissssiinngg iinnffoorrmmaattiioonn iinn tthhee Answer:
relativity ddiiEEddii EEnnssiinntteessttiieennii nn Δk :What ccoonntteexxtt aanndd rreettuurrnn aass NN ssuubb--qquueessttiioonnss.. …… Photoelectric
PPrrooppoosseedd aaaacccchhhhiiiieeeevvvveeee???? k :W1 hat did
PPPrrrooopppooossseeeddd aaaacccchhhhiiiieeeevvvveeee???? 1
d E id in E st i e n i s n te in QQ::{{QQuueessttiioonn}} QQuueessttiioonn effect
mm ee TTT qq rrr aa uu eee hhhss ii ss lll vv eee–– aaa aa eeooo ttt ll nn ee iii rrree vvv nn yyyrr cc iii gg ee ttt oooyy yyy fff EE AA iinn ll AA bb sstt ee lleebb rr iiee tt nn rrtt a a c c h h ie ie v v e e ? ? CCoonntteexxtt::
IInniittiiaall KKGG EEiinnsstteeiinn
pprrooppoosseedd EExxttrraacctt <<hh,, rr,, tt>> || <<sseenntteennccee>>
pprrooppoosseedd EExxttrraacctt
PPrriioorr RRoouunnddss AAdddd mm
eeqq
aa
mmuu
ss
iiaa
ss
vv
––
ssaass
ee
ll––
nn
eeee
ee
nnnn
rr
ccee
gg
eerr
yy
gg yy
……
eeqquuiivvaalleennccee
CCuurrrreenntt RRoouunndd AAdddd
Round N
RRRooouuunnnddd 111
RRRooouuunnnddd 000
Figure 2: Workflow of TCR-QF. Including a continuously mutual enhancement knowledge flow: (1) Forward Flow: The KG enhances
the LLM during answer generation with triple context restoration. (2) Feedback Flow: Identified missing knowledge through query-driven
feedback and reinforced into the KG.
(i)
where ∆K represents the knowledge increment corre- where θ is a predefined threshold. This consolidates synony-
sponding to the missing knowledge. This increment is up- mous entities, ensuring accurate representation of entities and
dated in the KG as triples, resulting in the more comprehen- relationships in the KG.
(i+1)
sive KG G .
3.2 Subgraph Retrieval
3.1 Knowledge Graph Construction
The subgraph retrieval phase focuses on extracting pertinent
An initial KG was constructed from raw textual data using information from the KG in response to the query. Specifi-
LLMs to extract entities and relations as triples (e , r, e ), cally, given a query Q expressed in natural language, the re-
h t
where entities include names, types Type(e), and descriptions trieval stage aims to extract the most relevant elements (e.g.,
Desc(e). Source document information is retained in each entities, triplets, paths, subgraphs) from KGs, which can be
node for provenance. The construction involves: formulated as:
Document Splitting Each document D of length L is di- ∗
G = G-Retriever(Q, G)
vided into overlapping chunks C with maximum length
i
MAX_LEN = 2048 and overlap OVERLAP = 256 tokens: = arg max Sim(Q, G),
G⊆R(G)
C = D[s : e ],
i i i ∗
where G = {(h , r , s ), (h , r , s ), . . . , (h , r , s )}
0 0 1 1 1 2 t t t+1
s = (i − 1) × (MAX_LEN − OVERLAP) + 1,
is the optimal retrieved graph elements and Sim(·, ·) is a
i
e = min(s + MAX_LEN − 1, L). function that measures the semantic similarity between user
i i
queries and the graph data. R(G) represents a function to
The overlap ensures entities and relations spanning across
narrow down the search range of subgraphs, considering effi-
chunks are captured.
ciency. The retrieval method employed in the TCR-QF builds
upon existing KG retrieval method [Sun et al., 2023], which
Triple Extraction From each chunk C , the LLM extracts
i
utilize LLMs to perform a beam search over the KG, with
triples:
iterative pruning guided by the LLM.
T = ExtractTriples(C ),
i i
where T is the set of triples from C . A specialized prompt
3.3 Triple Context Restoration
i i
guides the LLM to output structured information, including
The structuring of unstructured text into triples can lead to a
entity types and descriptions.
loss of semantic context. To address this issue, a triple con-
Subgraph Merging Extracted triples form subgraphs G =
text restoration mechanism was implemented in TCR-QF to
i
(V , E ). A unified KG G = (V, E) is constructed by merg-
restore semantic integrity by tracing back to the original tex-
i i
ing entities referring to the same concept using a similarity
tual context of the triples.
function Sim(e , e ) based on names, types, and descriptions:
a b
Context Retrieval For each triple (e , r, e ) in the retrieved
h t
Sim(e , e ) ≥ θ =⇒ e ≡ e , subgraphs, the source documents associated with the head
a b a b


| Physics enriched subgraph --ggooaall--
Germ w an a y s born in r N ec o e b P iv e h l e y d d P s i r i s c i c z s o e v i e n r ed Pho e to ff e e l c e t ctric S R u e b tr g i r e a v p a h l di E s A c i o n lb v s r e t e e e r r c i e t n e d d iv e e v d eloped T re h la eo ti r v y it o y f TTTT RRRR TTTT RRRR eeee eeee TTTT RRRR eeee mmmm eeee tttt mmmm eeee rrrr eeee tttt pppp mmmm iiii rrrr pppp tttt llll eeee iiii aaaa rrrr pppp llll eeee vvvv iiii aaaa tttt llllRRRR eeee eeee vvvv tttt aaaa aaaa RRRR eeee vvvv tttt aaaa llllRRRR eeee aaaa llll llll gggg nnnniiiiccccaaaarrrr TTTT tttt xxxxeeeetttt nnnn oooo CCCC gggg nnnniiiiccccaaaarrrr TTTT tttt xxxxeeeetttt nnnn oooo CCCC nnnniiiiccccaaaarrrr TTTT tttt xxxxeeeetttt nnnn oooo CCCC HHH EEE PPP ddd AAA HHH iiiEEE PPPrrr eee iii nnn ddd AAAlll iii sss HHH iii bbb sss EEE PPPrrr eee iii zzz nnn ddd rrr ccc tttAAAllleee iii sssppp iii eeebbb sss eee rrr eee eee iii zzz nnn rrr ooo rrr ccc tttiiillleee iii ttt ssshhhppp eee ccc nnnbbb sss eee eee zzz rrr vvvooo iiirrr ccc tttiiieee ooo ttt eee hhhppp nnn eee ccc nnn eee eee eee rrr vvvooo iii iii iii ddd tttooo ttt eee hhh nnn ccc nnn rrr vvv oooeeevvv PPP iii iii iii ddd ttt yyy sss ooo eee nnnrrr eeevvv eeeoooeee ccc PPP iii hhhiii ddd ttt yyy sss ooo ddd lll eee rrr ooo vvv eeeooo ccc yyy PPP iii hhh eee vvv yyy sss ooo ddd lll fff eee ooo eee sss ccc yyy eee ttt ccc hhh eee vvv hhh ooo ddd rrr lll iii fffooo ttt ttt sssyyy eee ttt ccc eee ccc eee vvv hhh rrr eeehhh rrr iii ddd fffttt ttt sss iii eee tttsss ccc eee ccceee hhh rrr eee ccc hhh rrr iii ddd ,,, 111 ttt tttiii sss eee ccc eee hhh rrr eee ccc lll PPP ……… ddd 999 ,,, 111 eee iii sss aaa eee hhhccc lllfff 222 PPP ……… 999 ,,, 111 eee www aaa ooo fff hhh ,,, lll 111 fff 222 PPP ……… 999 eee eeettt eeewww aaa oooooo fff fffhhh fff ,,, 111 fff 222 ccc ooo eee tttfff eeewww eee NNN ooo oooooo fff eeefff fff ttt ,,, lll 111 fff ccc ooo eee tttfff eee eeeeee ccc NNN rrr ... ooo ooo eee ooo fff fff ttt lllccc ttt fff ccc ooo ttt fff eeeeee ccc NNNrrr ... ooo hhh ttt bbb hhh eee ooo ttt lllccc ttt rrr fff ttt eee ccc rrr iii... iiihhh ttt eee eee bbb hhh ooo ccc ccc ttt rrr sss ttt lll iii iiihhh ttt eee eee bbb hhh ccc rrr sss lll iii iii eee eee ccc sss lll A b C < S < S … A b C < S < S … ee o o o o h h h h oo nn ll u u u u 1 2 1 2 nn ss oo r r r r ww , , , , tt ww c c c c ee r r r r e e e e ee xx 1 2 1 2 ii r : : r : : tt nn , , , , :: < < < < tt ff t t t t hh oo s s s s 1 2 1 2 ee e e e e rr > > > > mm n n n n qq t t t t uu aa e e e e ee tt n n n n ii ss oo c c c c tt nn ii e e e e oo .. > > > > nn .... .. wwiitthh RRRRR RRRRR
Albert Photoelectric gggg QQ::{{QQuueessttiioonn}} QQQQuueeuusseettiissoottnniioonn
Einstein effect
proposed
developed mass–energy Question-driven Reasoning
Theory of equivalence Feedback
relativity
--ggooaall--
included r S el p a e t c iv ia it l y PPPPP EEEEE AA rr AAA rrr ii oo iiinnll ooo nnn pp bblllss ppp bbb oo ttee ssseerr ssooo ttt eeeii ee ttnneee rrr sssdd iii eee ttt nnn ddd kk dd 11kk aa iiEEddaa ::kk dd cc 11 WW aacciiEEii11 aa ::kk ddhh EE hh nn cc WW:: cc ii11 WW ii hh iihh ssiiEE hh nn :: eeee nnttWWaa iiii hh vv ssiivv ee hh ss eeee nn tt tt aa ee ttii aa ee vvvv ee hh sseenn dd ?? tttt ??ee tt aa ii ee ii ee ii nnnn dd ?? tt ?? dd ii ii nn dd RR RReeeettttrrrriieeiieevvvvaaaallll Δ d k Eid1 i k: n W1 Es :W ti h eni a s h nt ta e dt i n id I c Q I c Q dd oo :: ee nn {{ nn QQ ttee ttii xx uu ffyy tt ee ss aa tt tt nn hh ii dd oo ee nn mm rr }} ee ii tt ss uu ss rr ii nn nn QQ gg aa uu ss ee ii ss nn NN tt ff iioo oo ss nn rr uu mm bb aa --qq ttii uu oo ee nn ss tt ii ii nn oo nn tthh ss ee .. …… A P ef h n fe o s c w t t o e e r l : ectric
IInniittiiaall KKGG mmeeTTTqqrrr aauueee hhhssiiss lllvveee–– aaaaaeeooo tttllnneeiii rrree vvvnnyyyrrcciii gg eettt oooyy yyy fff EEAA pp iiEEnn rr llAA pp bb oo ssiinn rr ttee pp lleebb oo ss rr oo iittee pp ttnn ssee rr ooeeiittnnddss eedd EEEExxttxxrrttaarrccaattcctt aacchhieievvee?? C < C <hh oo ,, nn rr ttee ,, xx tt tt >> :: || <<sseenntteennccee>>
P P rr ii oo rr RR oo uunn dd ss AA dd dd mmeeqq aammeeuuss qqiiaassvvuu ––ssaaiissee vvll––nneeaaeeeennllnnrr eecceegg nneerryy ccgg eeyy ……
C C uu rr rr ee nntt RR oo uu nn dd AA dddd
Round N |  |  |
| --- | --- | --- |
|  | RRRooouuunnnddd 111 |  |
|  | RRRooouuunnnddd 000 |  |

| d | eveloped |
| --- | --- |

| Reasoning
Question-driven
Feedback
--ggooaall--
PPPPP EEEEE AA rr AAA rrr ii oo iiinnll ooo nnn pp bblllss ppp bbb oo ttee ssseerr ssooo ttt eeeii ee ttnneee rrr sssdd iii eee ttt nnn ddd kk dd 11kk aa iiEEddaa ::kk dd cc 11 WW aacciiEEii11 aa ::kk ddhh EE hh nn cc WW:: cc ii11 WW ii hh iihh ssiiEE hh nn :: eeee nnttWWaa iiii hh vv ssiivv ee hh ss eeee nn tt tt aa ee ttii aa ee vvvv ee hh sseenn dd ?? tttt ??ee tt aa ii ee ii ee ii nnnn dd ?? tt ?? dd ii ii nn dd RR RReeeettttrrrriieeiieevvvvaaaallll Δ d k Eid1 i k: n W1 Es :W ti h eni a s h nt ta e dt i n id I c Q I c Q dd oo :: ee nn {{ nn QQ ttee ttii xx uu ffyy tt ee ss aa tt tt nn hh ii dd oo ee nn mm rr }} ee ii tt ss uu ss rr ii nn nn QQ gg aa uu ss ee ii ss nn NN tt ff iioo oo ss nn rr uu mm bb aa --qq ttii uu oo ee nn ss tt ii ii nn oo nn tthh ss ee .. …… A P ef h n fe o s c w t t o e e r l : ectric
mmeeTTTqqrrr aauueee hhhssiiss lllvveee–– aaaaaeeooo tttllnneeiii rrree vvvnnyyyrrcciii gg eettt oooyy yyy fff EEAA pp iiEEnn rr llAA pp bb oo ssiinn rr ttee pp lleebb oo ss rr oo iittee pp ttnn ssee rr ooeeiittnnddss eedd EEEExxttxxrrttaarrccaattcctt aacchhieievvee?? C < C <hh oo ,, nn rr ttee ,, xx tt tt >> :: || <<sseenntteennccee>>
mmeeqq aammeeuuss qqiiaassvvuu ––ssaaiissee vvll––nneeaaeeeennllnnrr eecceegg nneerryy ccgg eeyy ……
Round |  |
| --- | --- |
|  | Round |
and tail entities were retrieved: Knowledge Graph Enrichment For each missing compo-
(0)
nent k ∈ ∆K , a dense retriever interacted with the origi-
Sources = Sources(e ) ∪ Sources(e ).
q
(e ,e ) h t
h t
nal text sources D to retrieve relevant textual information and
These sources were the documents which the entities were
extract the missing knowledge:
originally extracted during KG construction. This set encom-
passed all documents potentially containing contextual infor- D = DenseRetrieve(k , D),
relevant q
mation about the relationship between e and e .
h t
k = ExtractTriples(k , D ),
q relevant
Triple Context Tracing To trace the context of the triple
where ExtractTriples employs the LLM to find and extract
(e , r, e ), the most relevant sentence from source documents
h t
the needed information, resulting in triples k corresponding
were identified. A template T was used, such as:
(e ,r,e )
h t
to the missing knowledge. The KG was then updated:
T = “e r e ”.
(e ,r,e ) h t
h t
(1) (0) (0) (0) (0)
G = G ∪ ∆K with ∀ k ∈ ∆K , k ∈/ G .
A pretrained embedding model f was used to generate
embed
embeddings for both the template and candidate sentences.
Duplicate relationships were filtered based on edit distance
The context relevance was assessed via cosine similarity:
(0) (1)
from elements in G to maintain uniqueness in G .
v = f (T ), v = f (s), ∀s ∈ S,
A dense passage retriever, implemented using OpenAI’s
T embed (e ,r,e ) s embed
h t
text-embedding-small, was employed due to its ef-
⊤
v v
s
T
sim(v , v ) =
fectiveness in retrieving semantically relevant passages.
T s
∥v ∥ · ∥v ∥
T s
(1)
Iterative Reasoning and Update The updated KG G
where S is the set of all sentences extracted from
was used to generate a new answer by following the reasoning
Sources . The sentence with the highest similarity score
(e ,e )
h t
steps:
was selected to provide contextual information into the triple.
Triple Augmentation Each triple was augmented with its (1)
(1)
A = LLM_Generate(FormatInput(Q, G )).
LLM
associated contextual sentence:
This iterative process continued, repeating the steps of Miss-
(e , r, e ) −→ (e , r, e , S ).
h t h t top
ing Knowledge Identification and Knowledge Graph Enrich-
This augmentation restored the contextual information of the
ment:
triples, improving the accuracy and depth of inference tasks
(i−1)
(i) (i−1)
that rely on the KG. ∆K = IdentifyMissing(Q, A , G ),
LLM
(i) (i−1) (i)
G = G ∪ ∆K ,
3.4 Iterative Reasoning with Query-driven
Feedback
(i)
(i)
A = LLM_Generate(FormatInput(Q, G )),
LLM
To generate accurate answers to the original queries Q, an it-
(i)
erative reasoning process incorporating a query-driven feed- for i = 2, 3, . . ., until ∆K = ∅ or a predefined maxi-
back mechanism was implemented. This approach dynam- mum number of iterations I = 20 was reached. By ana-
max
ically enriches the KG by identifying and updating missing lyzing retrieved contexts and generated responses at each it-
information during the reasoning process, thereby enhancing eration, gaps in the KG were detected and addressed, contin-
‘
the LLM s capability to produce more accurate responses. uously optimizing the KG and enhancing the reasoning capa-
′(0) bilities of the LLM.
Initially, the enriched subgraph G obtained from triple
Due to page limits, the detailed prompts used for the LLM
context restoration was used to prompt the LLM:
in each step are documented in the supplementary material.
(0) ′(0)
I = FormatInput(Q, G ).
(0) 4 Experiments
The LLM then generated an initial answer A by process-
LLM
ing this prompt:
To evaluate the effectiveness of the TCR-QF on question-
answering tasks, experiments were conducted on 5 question-
(0)
(0)
A = LLM_Generate(I ),
answering datasets: 2WikiMultiHopQA [Ho et al., 2020],
LLM
where LLM_Generate refers to generating a response HotpotQA [Yang et al., 2018], ConcurrentQA [Arora et
based on the formatted input I (0) . al., 2023], MuSiQue-Ans and MuSiQue-Full [Trivedi et al.,
2022] . Followed the settings outlined in [Yang et al., 2018],
Missing Knowledge Identification The initial answer and
utilizing a collection of related contexts for each pair as the
contexts were analyzed to identify missing information re-
retrieval corpus. Exact Match (EM) and F1 score were pre-
quired for the query:
sented as the evaluation metrics across all datasets.
(0) We compared TCR-QF with representative methods from
(0) ′(0)
∆K = IdentifyMissing(Q, A , G ),
LLM
LLMs and RAG:
(0)
where ∆K represents the set of missing knowledge,
(1) LLM Only: Methods that directly use LLMs for obtain-
formalized as a series of sub-questions. The function
ing answers, including models such as gpt-4o-mini and
(0)
IdentifyMissing utilizes the LLM to compare Q with A gpt-4o, as well as chain-of-thought (CoT) [Wei et al., 2022]
LLM
′(0)
and G , effectively harnessing its understanding to identify prompting strategies.
gaps in knowledge. (2) Text-based RAG: Methods that employ a dense retriever

to retrieve relevant text chunks from a text corpus and gen- On the MuSiQue-Full dataset, TCR-QF achieves an EM score
erate answers by leveraging this information. For this cat- of 0.303, compared to GraphRAG’s EM score of 0.189. This
1
egory, LangChainQ&A was used as a representative naive represents an absolute increase of 0.114, amounting to an im-
RAG method, which is well-known and widely used. provement of approximately 60.3%. These significant gains
(3) Graph-based RAG: Methods that retrieve subgraphs demonstrate that TCR-QF effectively leverages knowledge to
from KG to enhance LLM. ToG [Sun et al., 2023] was se- enhance the LLM’s performance beyond what is achieved
lected as a representative for comparison in this category. by simply combining text and graph data. By dynamically
(4) Hybrid RAG: Methods like GraphRAG [Edge et al., restoring lost semantic information and enriching the KG dur-
2024] that retrieve information from both KG and textual doc- ing reasoning, TCR-QF provides a more comprehensive con-
uments to augment LLM. text for the LLM, leading to better reasoning and answer gen-
eration in complex tasks.
Experimental Settings: For all comparison meth-
The consistent superiority of TCR-QF across multiple
ods and the TCR-QF, unless otherwise specified, the
—
datasets ranging from general question-answering to those
gpt-4o-mini-2024-07-18 model was utilized, as it is
—
requiring multi-hop reasoning highlights TCR-QF’s robust-
more cost-effective and faster than gpt-3.5-turbo. Due
ness and general applicability. TCR-QF effectively addresses
to the high computational costs associated with inference on
the challenges posed by incomplete KGs and information
the full dataset, 1,200 samples were randomly selected from
— loss, leading to more accurate and complete responses.
each of the larger datasets 2WikiMultiHopQA, HotpotQA,
—
MuSiQue-Full, and MuSiQue-Ans for testing to conserve
4.2 Ablation Study
computational resources. For ConcurrentQA, 1,600 samples
from the complete test set were evaluated.
To evaluate the individual contributions of the proposed com-
ponents, namely triple context restoration (TCR) and query-
4.1 Results and Findings
driven feedback (QF), to the overall performance of the TCR-
Table 1 presents the comparative results, from which we an-
QF, an ablation study was conducted on the 2WikiMulti-
swer the following Research Question (RQ).
HopQA and HotpotQA datasets to answer the question:
RQ1 How does the TCR-QF improve the completeness and
RQ2 In what ways does each component in TCR-QF en-
accuracy of information retrieval in question answering
hance the reasoning of the LLM?
tasks compared to the existing GraphRAG methods?
Table 1 demonstrates the superiority of the TCR-QF com- Table 2 presents the results of the ablation experiments.
pared to different methods on five benchmark question an- The full TCR-QF is compared with several ablated variants:
swering datasets. TCR-QF consistently achieves the highest
• ToG (w/o TCR & QF): The baseline method operating
EM and F1 scores across all datasets, demonstrating its su-
on the KG.
perior effectiveness in enhancing LLMs for complex reason-
ing tasks. Compared to the LLM-only approaches (GPT-
• TCR (w/o QF): Incorporates triple context restoration
4o-mini, GPT-4o and CoT), TCR-QF shows substantial im-
alone to address contextual information loss.
provements. For instance, on the HotpotQA dataset, TCR-
• QF (w/o TCR): Employs query-driven feedback alone
QF attains an EM score of 0.558, which is 0.207 higher than
to approach incomplete information extraction.
GPT-4o’s score of 0.351, representing a relative improvement
of approximately 59%. This indicates that while LLMs pos-
• TCR-AF: Integrate triple context restoration with
sess strong language understanding capabilities, integrating
answer-driven feedback (AF) which involves directly
external knowledge as TCR-QF does markedly enhances their
extracting triples from the LLM’s answer and adding
accuracy in answering complex questions.
them to the KG.
When contrasting TCR-QF with the text-based method
(Naive RAG) and the graph-based method (ToG), TCR- From the results we can draw the following insights.
QF exhibits notable performance gains. Specifically, on the
Effectiveness of Triple Context Restoration (TCR).
2WikiMultiHopQA dataset, TCR-QF achieves an EM score
Comparing the baseline ToG method with the TCR vari-
of 0.598, which is an absolute increase of 0.259 over Naive
— ant, it can be observed that introducing triple context restora-
RAG’s EM score of 0.339 a relative improvement of ap-
tion leads to significant performance improvements. On the
proximately 76.4%. Similarly, TCR-QF surpasses TOG’s
2WikiMultiHopQA dataset, the EM score increases from
EM score of 0.400 by an absolute margin of 0.198, reflect-
0.400 to 0.481, representing an improvement of 20.25%,
ing a 49.5% improvement. This significant enhancement in-
while the F1 score rises from 0.476 to 0.561. Similarly, on
dicates that TCR-QF’s approach of enriching the LLM with
the HotpotQA dataset, the EM score improves from 0.420 to
more comprehensive knowledge markedly improves reason-
0.494 (a 17.62% improvement), and the F1 score increases
ing, outperforming methods that rely solely on retrieved texts
from 0.555 to 0.642. These enhancements confirm that triple
or static KGs.
context restoration effectively mitigates contextual informa-
Furthermore, TCR-QF outperforms the hybrid method
tion loss by reconnecting structured triples with their original
(GraphRAG), which combines text and graph information.
textual context, thereby enriching the semantic information
1 https://python.langchain.com/docs/tutorials/rag available for reasoning.

2WikiMultiHopQA HotpotQA MuSiQue-Full MuSiQue-Ans ConcurrentQA
Method Type Method
EM F1 EM F1 EM F1 EM F1 EM F1
GPT-4o-mini 0.266 0.320 0.273 0.381 0.048 0.132 0.052 0.135 0.112 0.178
GPT-4o 0.311 0.364 0.351 0.475 0.089 0.193 0.104 0.215 0.176 0.247
LLM only
CoT 0.287 0.354 0.299 0.420 0.093 0.196 0.117 0.219 0.134 0.203
Text-based Naive RAG 0.339 0.391 0.411 0.530 0.111 0.207 0.122 0.221 0.363 0.443
Graph-based TOG 0.400 0.476 0.420 0.555 0.136 0.237 0.160 0.269 0.278 0.359
Hybrid GraphRAG 0.485 0.626 0.495 0.645 0.189 0.326 0.258 0.395 0.459 0.582
Proposed TCR-QF 0.598 0.680 0.558 0.708 0.303 0.432 0.366 0.489 0.492 0.597
Table 1: Main Results. Performance comparison of different methods across five question answering datasets.
2WikiMultiHopQA HotpotQA
Methods 0.600
EM F1 EM F1 0.575
0.550
ToG(w/o TCR&QF) 0.400 0.476 0.420 0.555
0.525
TCR(w/o QF) 0.481 0.561 0.494 0.642
0.500
QF(w/o TCR) 0.568 0.651 0.515 0.656
0.475
TCR-AF 0.538 0.619 0.531 0.682
0.450
TCR-QF 0.598 0.680 0.558 0.708
0.425
0.400
Table 2: Ablation experiment results on the 2WikiMultiHopQA
0 1 2 3 4 5 6 7 8 9
Round
and HotpotQA datasets. TCR stands for triple context restoration,
QF stands for query-driven feedback. TCR-AF indicates replacing
query-driven feedback with answer-driven feedback which directly
extract triples from the answers and feed them back into the KG.
Effectiveness of Query-Driven Feedback (QF). The QF
variant, which focuses on dynamically updating the KG based
on the requirements of the query, shows even greater im-
provements over the baseline. The EM scores rise to 0.568
(a 42.00% improvement) on 2WikiMultiHopQA and 0.522 (a
24.29% improvement) on HotpotQA. These substantial gains
indicates that query-driven feedback significantly addresses
the issue of incomplete information extraction. By dynam-
ically enriching the KG based on the specific requirements
of the query, the model fills in the missing knowledge that
static KGs might overlook due to limitations in initial extrac-
tion algorithms. This adaptive approach continually enhances
the relevance and comprehensiveness of the knowledge graph
throughout the reasoning process.
Synergy of TCR and QF. The full TCR-QF method,
which combines both triple context restoration and query-
driven feedback, achieves the highest performance. EM
scores reach 0.598 on 2WikiMultiHopQA and 0.558 on Hot-
potQA, with relative improvements of 49.50% and 32.86%
over the baseline, respectively. These results underscore a
synergistic effect when combining TCR and QF, as the model
benefits from both restored contextual semantics and a dy-
namically enriched KG. The integration of both components
effectively addresses the dual challenges of information loss,
leading to more accurate and complete reasoning.
Comparison with Answer-Driven Feedback (TCR-AF).
The TCR-AF variant replaces query-driven feedback with
answer-driven feedback, where triples are extracted from the
model’s answers to update the KG. While TCR-AF outper-
forms ToG, achieving EM scores of 0.538 on 2WikiMulti-
ME
2WikiMultiHopQA
0.600
0.575
0.550
0.525
0.500
0.475
0.450
0.425
0.400
0 1 2 3 4 5 6 7 8 9
Round
ME
HotpotQA
RTQF RTAF QF RT ToG
Figure 3: Comparative ressults from the ablation study. EM per-
formance of different methods across rounds on 2WikiMultiHopQA
and HotpotQA.
HopQA and 0.523 on HotpotQA, it falls short compared to
TCR-QF. TCR-QF scores 0.598 on 2WikiMultiHopQA, an
11.12% increase over TCR-AF. This suggests that enriching
the KG proactively based on the query is more effective than
reactively updating it based on answers, likely because it pre-
vents error propagation from incomplete initial reasoning.
Performance Trends Across Rounds. Figure 3 illustrates
the EM performance across multiple reasoning rounds for
each method. It is evident that TCR-QF consistently out-
performs other variants from the initial rounds and maintains
its lead as the reasoning progresses. The performance gain
from TCR-QF is additive, with TCR-QF achieving the high-
est accuracy. The diminishing returns after a few rounds in-
dicate that the most significant knowledge enrichment occurs
early in the reasoning process, emphasizing the performance
of proposed method.
In conclusion, the ablation study corroborates our initial
hypotheses, demonstrating that both triple context restora-
tion and query-driven feedback are vital in addressing the in-
herent limitations of integrating KGs with LLMs. Individu-
ally, each component contributes significantly to performance
improvements by targeting specific sources of information
—
loss triple context restoration restores essential contextual
semantics lost during the structuring process, while query-
driven feedback dynamically enriches the KG to address in-
complete information extraction. These results highlight the
effectiveness of restoring semantic integrity and continuously
updating the KG during reasoning, fulfilling our research ob-
jectives and underscoring the importance of a bidirectional


|  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |

|  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
knowledge flow in optimizing reasoning outcomes.
4000
4.3 Statistical and Convergence Analysis
3500
To evaluate the effectiveness and convergence of the TCR-
3000
QF, statistical analyses were conducted over multiple infer-
ence rounds. Table 3 presents key metrics from the initial
2500
round to the 10th round, including the numbers of nodes and
2000
edges in the KG, as well as the EM and F1 scores on the
1500
2WikiMultiHopQA dataset. These experiments and results
provide answers to the following question: 1000
RQ3 How do TCR-QF continuously enhance KG and boost 500
LLM reasoning?
0
1 2 3 4 5 6 7 8 9 10
Inference Rounds
2WikiMultiHopQA
Rounds Nodes Edges EM F1
0 74,571 69,866 0.481 0.562
1 76,441 74,006 0.555 0.637
2 77,377 76,615 0.581 0.662
3 77,937 78,265 0.589 0.671
4 78,259 79,258 0.593 0.676
5 78,450 79,840 0.593 0.675
6 78,570 80,150 0.597 0.679
7 78,630 80,310 0.597 0.679
8 78,650 80,403 0.598 0.680
9 78,656 80,446 0.598 0.680
10 78,661 80,472 0.598 0.680
∆ 4,090 10,606 0.117 0.118
Table 3: Statistics from the initial round to the 10th round on 2Wiki-
MultiHopQA dataset, where ∆ denotes the cumulative increase.
From the results we can draw the following insights.
Continuous Improvement of KG Completeness and
Model Reasoning Performance. As demonstrated in Ta-
ble 3, the TCR-QF significantly enriches the KG over suc-
cessive inference rounds. Specifically, on the 2WikiMulti-
HopQA dataset, the number of nodes in the KG increased by
4,090 (from 74,571 to 78,661), and the number of edges in-
creased by 10,606 (from 69,866 to 80,472) over 10 rounds.
This enrichment directly addresses the issue of information
sparsity by incorporating previously missing triples and ex-
panding the KG’s coverage to meet query demands. Cor-
respondingly, the model’s reasoning performance improved
substantially. The Exact Match (EM) score increased from
0.481 to 0.598, a 24.3% improvement, and the F1 score rose
from 0.562 to 0.680, a 21.0% improvement. These significant
performance gains indicate that the enriched KG provides the
LLM with more comprehensive and contextually rich infor-
mation, directly mitigating the effects of context loss and en-
hancing reasoning accuracy.
Alignment of KG Completeness and Reasoning Perfor-
mance Enhancement. As depicted in Figure 4, the parallel
upward trends in KG metrics and performance scores affirm a
strong correlation between the enriched KG and the model’s
improved reasoning ability. By restoring the contextual infor-
mation associated with triples and integrating new, relevant
knowledge through query-driven feedback, the TCR-QF en-
hances the semantic integrity of the KG. This comprehensive
knowledge base enables the LLM to perform more accurate
tnuoC
esaercnI
Growth Trend over Inference Rounds
4140
New Triples Added (vs. Previous Round)
New Entities Added (vs. Previous Round)
0.07
F1 Improvement (vs. Previous Round)
EM Improvement (vs. Previous Round)
0.06
0.05
2609
0.04
1870
0.03
1650
0.02
993
936
0.01
582
560
322 310
191 160 0.00
120 93
60 20 43 6 26 5
tnemevorpmI
erocS
Figure 4: Trends in KG growth and inference performance improve-
ment over rounds on 2WikiMultiHopQA.
and context-aware reasoning, directly addressing the limita-
tions posed by information sparsity and context loss.
Convergence of KG Enrichment and Performance Im-
provements. The TCR-QF not only enriches the KG but
also exhibits convergence over inference rounds, ensuring ef-
ficient use of computational resources. As illustrated in Fig-
ure 4, both the growth of the KG and the improvement in
performance metrics begin to plateau after several rounds,
specifically between the 8th and 10th iterations. The incre-
mental increases in nodes and edges diminish, and the EM
and F1 scores stabilize at 0.598 and 0.680, respectively. This
convergence suggests that the TCR-QF effectively enriches
the KG to an optimal level, beyond which additional itera-
tions yield minimal benefits.
The experimental results validate the effectiveness of the
TCR-QF in overcoming the foundational challenges outlined
in the introduction. By continuously and efficiently enhanc-
ing the KG’s completeness and restoring lost contextual nu-
ances, the TCR-QF significantly boosts the model’s reason-
ing performance. These findings confirm that addressing in-
formation loss through dynamic KG enrichment and context
restoration is a viable and efficient strategy for advancing the
integration of KGs and LLMs in complex reasoning tasks.
5 Conclusion
This paper presents TCR-QF, a novel framework that inte-
grates knowledge graphs (KGs) with large language mod-
els (LLMs) to advance complex reasoning for question-
answering tasks. By addressing two primary sources of in-
formation lossm namely, context loss through triple context
restoration (TCR) and incomplete extraction via query-driven
feedback (QF), our TCR-QF framework recovers essential se-
mantic details and dynamically expands the KG as the model
reasons. Extensive evaluations on five benchmark datasets
demonstrate that TCR-QF significantly outperforms the state-
of-the-art competitors, demonstrating the value of incorporat-
ing contextualized triples and iterative KG updates in enhanc-
ing LLM performance. These results highlight the potential
of TCR-QF to bridge the gap between structured and unstruc-
tured knowledge, paving the way for more accurate and ro-
bust AI-driven reasoning across diverse domains.


|  |  |  |  |  |  |  |  |  |  |  | N
N
F | ew Triple
ew Entiti
1 Improv | s Added
es Adde
ement (v | (vs. Pre
d (vs. Pr
s. Previo | vious Ro
evious R
us Roun | und)
ound)
d) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  | E | M Improv | ement ( | vs. Previ | ous Rou | nd) |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | 260 |  |  | 9 |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | 1 | 870 |  |  | 165 |  |  | 0 |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  | 936 |  |  | 993 |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  | 560 |  | 582
322 | 310
191 | 120 160 | 93 |  |  |  |
References [Li et al., 2023] Bo Li, Gexiang Fang, Yang Yang, Quansen
Wang, Wei Ye, Wen Zhao, and Shikun Zhang. Evaluat-
[Arora et al., 2023] Simran Arora, Patrick S. H. Lewis, An-
ing chatgpt’s information extraction capabilities: An as-
gela Fan, Jacob Kahn, and Christopher Ré. Reasoning over
sessment of performance, explainability, calibration, and
public and private data in retrieval-based systems. Trans.
faithfulness. CoRR, abs/2304.11633, 2023.
Assoc. Comput. Linguistics, 11:902–921, 2023.
[Liang et al., 2024] Lei Liang, Mengshu Sun, Zhengke Gui,
[Biswas et al., 2024] Russa Biswas, Harald Sack, and
Zhongshu Zhu, Zhouyu Jiang, Ling Zhong, Yuan Qu,
Mehwish Alam. MADLINK: attentive multihop and en-
Peilong Zhao, Zhongpu Bo, Jin Yang, Huaidong Xiong,
tity descriptions for link prediction in knowledge graphs.
Lin Yuan, Jun Xu, Zaoyang Wang, Zhiqiang Zhang, Wen
Semantic Web, 15(1):83–106, 2024.
Zhang, Huajun Chen, Wenguang Chen, and Jun Zhou.
[Chen et al., 2024a] Hanzhu Chen, Xu Shen, Qitan Lv, Jie Kag: Boosting llms in professional domains via knowl-
Wang, Xiaoqi Ni, and Jieping Ye. SAC-KG: exploiting edge augmented generation. CoRR, abs/2409.13731,
large language models as skilled automatic constructors 2024.
for domain knowledge graphs. CoRR, abs/2410.02811,
[Munikoti et al., 2023] Sai Munikoti, Anurag Acharya,
2024.
Sridevi Wagle, and Sameera Horawalavithana. AT-
[Chen et al., 2024b] Weijie Chen, Ting Bai, Jinbo Su, Jian LANTIC: structure-aware retrieval-augmented lan-
Luan, Wei Liu, and Chuan Shi. Kg-retriever: Efficient guage model for interdisciplinary science. CoRR,
knowledge indexing for retrieval-augmented large lan- abs/2311.12289, 2023.
guage models. CoRR, abs/2412.05547, 2024.
[Pan et al., 2024] Shirui Pan, Linhao Luo, Yufei Wang, Chen
[Cohen et al., 2023] William W. Cohen, Wenhu Chen, Chen, Jiapu Wang, and Xindong Wu. Unifying large lan-
guage models and knowledge graphs: A roadmap. IEEE
Michiel de Jong, Nitish Gupta, Alessandro Presta, Pat
Trans. Knowl. Data Eng., 36(7):3580–3599, 2024.
Verga, and John Wieting. QA is the new KR: question-
answer pairs as knowledge bases. In Proceedings of 37th
[Panda et al., 2024] Pranoy Panda, Ankush Agarwal, Chai-
Conference on AAAI, pages 15385–15392. AAAI Press,
tanya Devaguptapu, Manohar Kaul, and Prathosh A P.
2023.
HOLMES: hyper-relational knowledge graphs for multi-
hop question answering using llms. In Proceedings of
[Delile et al., 2024] Julien Delile, Srayanta Mukherjee, An-
62nd Conference on ACL, pages 13263–13282. ACL,
ton Van Pamel, and Leonid Zhukov. Graph-based retriever
2024.
captures the long tail of biomedical knowledge. CoRR,
abs/2402.12352, 2024.
[Paulheim, 2017] Heiko Paulheim. Knowledge graph refine-
ment: A survey of approaches and evaluation methods. Se-
[Edge et al., 2024] Darren Edge, Ha Trinh, Newman Cheng,
mantic Web, 8(3):489–508, 2017.
Joshua Bradley, Alex Chao, Apurva Mody, Steven Tru-
itt, and Jonathan Larson. From local to global: A graph
[Peng et al., 2024] Boci Peng, Yun Zhu, Yongchao Liu, Xi-
RAG approach to query-focused summarization. CoRR,
aohe Bo, Haizhou Shi, Chuntao Hong, Yan Zhang, and
abs/2404.16130, 2024.
Siliang Tang. Graph retrieval-augmented generation: A
survey. CoRR, abs/2408.08921, 2024.
[He et al., 2024] Xiaoxin He, Yijun Tian, Yifei Sun,
Nitesh V. Chawla, Thomas Laurent, Yann LeCun, Xavier [Soman et al., 2024] Karthik Soman, Peter W Rose, John H
Bresson, and Bryan Hooi. G-retriever: Retrieval-
Morris, Rabia E Akbas, Brett Smith, Braian Peetoom,
augmented generation for textual graph understanding and
Catalina Villouta-Reyes, Gabriel Cerono, Yongmei Shi,
question answering. CoRR, abs/2402.07630, 2024.
Angela Rizk-Jackson, et al. Biomedical knowledge graph-
optimized prompt generation for large language models.
[Ho et al., 2020] Xanh Ho, Anh-Khoa Duong Nguyen, Saku
Bioinformatics, 40(9):btae560, 2024.
Sugawara, and Akiko Aizawa. Constructing a multi-hop
QA dataset for comprehensive evaluation of reasoning [Sun et al., 2023] Jiashuo Sun, Chengjin Xu, Lumingyuan
steps. In Donia Scott, Nuria Bel, and Chengqing Zong,
Tang, Saizhuo Wang, Chen Lin, Yeyun Gong, Heung-
editors, Proceedings of the 28th ICCL, pages 6609–6625.
Yeung Shum, and Jian Guo. Think-on-graph: Deep and re-
ICCL, December 2020.
sponsible reasoning of large language model with knowl-
edge graph. CoRR, abs/2307.07697, 2023.
[Jiang et al., 2023] Jinhao Jiang, Kun Zhou, Zican Dong,
Keming Ye, Xin Zhao, and Ji-Rong Wen. Structgpt: A [Sun et al., 2024] Qiang Sun, Yuanyi Luo, Wenxiao Zhang,
general framework for large language model to reason over Sirui Li, Jichunyang Li, Kai Niu, Xiangrui Kong, and
structured data. In Proceedings of Conference on EMNLP Wei Liu. Docs2kg: Unified knowledge graph construction
2023, pages 9237–9251. ACL, 2023. from heterogeneous documents assisted by large language
models. CoRR, abs/2406.02962, 2024.
[Kim et al., 2023] Jiho Kim, Yeonsu Kwon, Yohan Jo, and
Edward Choi. KG-GPT: A general framework for rea- [Taunk et al., 2023] Dhaval Taunk, Lakshya Khanna, Siri
soning on knowledge graphs using large language models. Venkata Pavan Kumar Kandru, Vasudeva Varma, Charu
In Findings of the EMNLP 2023, pages 9410–9421. ACL, Sharma, and Makarand Tapaswi. Grapeqa: Graph aug-
2023. mentation and pruning to enhance question-answering. In

Ying Ding, Jie Tang, Juan F. Sequeda, Lora Aroyo, Carlos
Castillo, and Geert-Jan Houben, editors, Companion Pro-
ceedings of the Conference on WWW 2023, pages 1138–
1144. ACM, 2023.
[Trisedya et al., 2019] Bayu Distiawan Trisedya, Jianzhong
Qi, and Rui Zhang. Entity alignment between knowledge
graphs using attribute embeddings. In Proceedings of Con-
ference on AAAI, volume 33, pages 297–304, 2019.
[Trivedi et al., 2022] Harsh Trivedi, Niranjan Balasubrama-
nian, Tushar Khot, and Ashish Sabharwal. Musique:
Multihop questions via single-hop question composition.
Trans. Assoc. Comput. Linguistics, 10:539–554, 2022.
[Wei et al., 2022] Jason Wei, Xuezhi Wang, Dale Schuur-
mans, Maarten Bosma, Brian Ichter, Fei Xia, Ed H. Chi,
Quoc V. Le, and Denny Zhou. Chain-of-thought prompt-
ing elicits reasoning in large language models. In Proceed-
ings of the 2022 Conference of NeurIPS, 2022.
[Xu et al., 2024a] Chengjin Xu, Muzhi Li, Cehao Yang,
Xuhui Jiang, Lumingyuan Tang, Yiyan Qi, and Jian Guo.
Move beyond triples: Contextual knowledge graph repre-
sentation and reasoning. arXiv preprint arXiv:2406.11160,
2024.
[Xu et al., 2024b] Derong Xu, Wei Chen, Wenjun Peng,
Chao Zhang, Tong Xu, Xiangyu Zhao, Xian Wu, Yefeng
Zheng, Yang Wang, and Enhong Chen. Large language
models for generative information extraction: a survey.
Frontiers Comput. Sci., 18(6):186357, 2024.
[Yang et al., 2018] Zhilin Yang, Peng Qi, Saizheng Zhang,
Yoshua Bengio, William W. Cohen, Ruslan Salakhutdinov,
and Christopher D. Manning. Hotpotqa: A dataset for di-
verse, explainable multi-hop question answering. In Pro-
ceedings of the Conference on EMNLP 2018, pages 2369–
2380. ACL, 2018.
[Yang et al., 2024] Linyao Yang, Hongyang Chen, Zhao Li,
Xiao Ding, and Xindong Wu. Give us the facts: Enhanc-
ing large language models with knowledge graphs for fact-
aware language modeling. IEEE Trans. Knowl. Data Eng.,
36(7):3091–3110, 2024.
[Yasunaga et al., 2021] Michihiro Yasunaga, Hongyu Ren,
Antoine Bosselut, Percy Liang, and Jure Leskovec. QA-
GNN: reasoning with language models and knowledge
graphs for question answering. In Proceedings of the 2021
Conference of NAACL, pages 535–546. ACL, 2021.
[Zhang and Soh, 2024] Bowen Zhang and Harold Soh. Ex-
tract, define, canonicalize: An llm-based framework for
knowledge graph construction. In Proceedings of the 2024
Conference on EMNLP, pages 9820–9836. ACL, 2024.
[Zhong et al., 2024] Lingfeng Zhong, Jia Wu, Qian Li, Hao
Peng, and Xindong Wu. A comprehensive survey on auto-
matic knowledge graph construction. ACM Comput. Surv.,
56(4):94:1–94:62, 2024.
[Zhu et al., 2024] Yuqi Zhu, Xiaohan Wang, Jing Chen,
Shuofei Qiao, Yixin Ou, Yunzhi Yao, Shumin Deng, Hua-
jun Chen, and Ningyu Zhang. Llms for knowledge graph
construction and reasoning: recent capabilities and future
opportunities. World Wide Web (WWW), 27(5):58, 2024.

A Prompt Templates used in TCR-QF Architecture Conference.
A.1 Prompt for Triples Extraction
Output:
[entity | Emily | person | Emily is an
"""
aspiring architect who feels awe when
--Goal--
observing the skyscrapers of New
Given a text document potentially
York City.]
relevant to this activity, identify
[entity | New York City | location | New
all entities from the text and all
York City is a major city known for
relationships among the identified
its towering skyscrapers.]
entities.
[entity | Dr. Smith | person | Dr. Smith
is Emily’s mentor who encourages her
-Steps-
to pursue a career in architecture.]
1. Identify all entities. For each
[entity | International Architecture
identified entity, extract the
Conference | event | An upcoming
following information:
event that Emily and Dr. Smith plan
- entity name: The name of the entity
to attend together.]
- entity type: The type of the entity (e
[relationship | Emily | mentored by | Dr
.g., person, organization, location,
. Smith ]
event)
[relationship | Emily | attends |
- entity description: A detailed
International Architecture Conference
description of the entity’s
]
attributes and activities in the text
[relationship | International
Format each entity as [entity | <entity
Architecture Conference | located in
name> | <entity type> | <entity
| New York City]
description>]
-Real Data-
Text:
2. Identify relationships among entities
{input_text}
. From the entities identified in
Step 1, find all pairs of [source
Output:
entity, target entity] that are
*
"""
clearly related .
*
For each pair of related entities,
extract the following information:
A.2 Prompt for Reasoning
- source entity: name of the source
entity, as identified in step 1 -Goal-
- target entity: name of the target Given a question and the associated
entity, as identified in step 1 retrieved knowledge graph triplets (
- relationship: The relationship between entity, relation, entity) and text
source entity and target entity information,
Format each relationship as [ you are asked to answer the question
relationship | <source entity> | < with these information and your
relationship> | <target entity>] knowledge.
Ensure that both source entity and -Attentions-
target entity come from the entity - Please strictly follow the format in
list extracted in Step 1. the example to answer, do not
The extraction entity names and provide additional content such as
relations should remain consistent explanations.
with the language used in the -Real - The answer needs to be as precise and
Data-. concise as possible such as "
Flatbush section of Brooklyn, New
-Examples- York City", "Christopher Nolan", "
Text: New York City".
Emily gazed at the towering skyscrapers - Ensure that the answer corresponds
of New York City, feeling a sense of exactly to the Question without
awe. Her mentor, Dr. Smith, had deviation.
always encouraged her to pursue -Example-
architecture. Together, they planned
to attend the upcoming International Triplets:

1. <Inception, released in, 2010> Triplets:
2. <Inception, genre, science fiction> 1. <Albert Einstein (type: Person), born
3. <Inception, directed by, Christopher in , Ulm (type: City)>
Nolan> 2. <Albert Einstein (type: Person), born
on, 14 March 1879 (type: Date)>
Text Information: 3. <Albert Einstein (type: Person),
1. Inception was released in 2010 and known for, theory of relativity (type
received critical acclaim, winning : Theory)>
several Academy Awards. 4. <Albert Einstein (type: Person), won
2. The film explores complex themes of Nobel Prize in, 1921 (type: Date)>
dreams and reality, captivating 5. <1921 Nobel Prize in Physics (type:
audiences. Award), awarded to, Albert Einstein (
3. Directed by Christopher Nolan, it type: Person)>
showcases his distinctive
storytelling style. Text Information:
1. Albert Einstein was born in Ulm.
Question: 2. He was born on 14 March 1879.
"Who directed the movie Inception?" 3. He is known for the theory of
relativity.
Output: 4. In 1921, Albert Einstein won the
Christopher Nolan Nobel Prize in Physics.
-Real Data- Question:
"For what did Albert Einstein receive
Triplets Information: the Nobel Prize in Physics?"
{triplets_text}
Output:
Text Information: What was the 1921 Nobel Prize in Physics
{text_information} awarded for?
Question: -Real Data-
{question} Triplets:
{triplets_text}
Output:
""" Text Information:
{text_information}
Question:
A.3 Prompt for Missing Knowledge Identification
"{quesion}"
Output:
"""
"""
-Goal-
Analyze the provided triples and text
information to identify what is
A.4 Prompt for Knowledge Graph Enrichment
missing for accurately answering the
question. Then, Present the missing -Goal-
parts as several independent Given a series of texts and some
questions. questions, extract triplet
information from the texts, focusing
-Attentions- on the triplets that can specifically
- Please strictly follow the format in answer the questions.
the example to answer, do not
provide additional content such as -Attentions-
explanations. - Please strictly follow the format in
- Ensure that all results are inferred the example to answer, do not
based on the information I provided. provide additional content such as
- Only provide questions about missing explanations.
information. - Ensure that all triples are inferred
based on the information I provided.
-Example- - Try to extract all the triples
related to the question from the

text.
- Each extracted triplet is returned in
the following format: <Albert
Einstein (type: Person), discover,
photoelectric effect (type:
Scientific Concept)>
-Example-
Text Information:
Albert Einstein was born in Ulm. He was
born on 14 March 1879.
He is known for the theory of relativity
.
In 1921, Albert Einstein won the Nobel
Prize in Physics.
The 1921 Nobel Prize in Physics was
awarded to him for his work on the
photoelectric effect.
Questions:
1. "For what did Albert Einstein receive
the Nobel Prize in Physics?"
2. "What was the 1921 Nobel Prize in
Physics awarded for?"
Output:
<Albert Einstein (type: Person), is a ,
physicist (type: Occupation)>
<Albert Einstein (type: Person),
discover, photoelectric effect (type:
Scientific Concept)>
<Albert Einstein (type: Person), was,
Nobel laureate (type: Awardee)]
<Albert Einstein, awarded Nobel Prize
for, photoelectric effect (type:
Scientific Concept)>
<1921 Nobel Prize in Physics (type:
Award), awarded to, Albert Einstein (
type: Person)>
-Real Data-
Text Information:
{text_information}
Questions:
{questions}
Output:
"""

