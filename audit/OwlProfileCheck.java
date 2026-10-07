import java.io.File;
import java.util.Map;
import java.util.TreeMap;

import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.OWLOntology;
import org.semanticweb.owlapi.model.OWLOntologyManager;
import org.semanticweb.owlapi.profiles.OWL2RLProfile;
import org.semanticweb.owlapi.profiles.OWLProfileReport;
import org.semanticweb.owlapi.profiles.OWLProfileViolation;

/** Run the OWL API's normative OWL 2 RL profile checker over a Turtle ontology. */
public final class OwlProfileCheck {
    private OwlProfileCheck() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: OwlProfileCheck ontology.ttl");
        }
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
        OWLOntology ontology = manager.loadOntologyFromOntologyDocument(new File(args[0]));
        OWLProfileReport report = new OWL2RLProfile().checkOntology(ontology);
        System.out.println("axioms=" + ontology.getAxiomCount());
        System.out.println("in_owl2_rl_profile=" + report.isInProfile());
        Map<String, Integer> counts = new TreeMap<>();
        for (OWLProfileViolation violation : report.getViolations()) {
            String key = violation.getClass().getSimpleName();
            counts.put(key, counts.getOrDefault(key, 0) + 1);
            System.out.println(violation.getClass().getSimpleName() + " | " + violation);
        }
        System.out.println("violation_count=" + report.getViolations().size());
        System.out.println("violation_types=" + counts);
        if (!report.isInProfile()) {
            System.exit(2);
        }
    }
}
