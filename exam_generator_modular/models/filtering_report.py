# models/filtering_report.py

class FilteringReport:
    """Class to track and report the filtering process"""
    
    def __init__(self):
        self.steps = []
        self.warnings = []
        self.suggestions = []
        self.final_count = 0
        self.initial_count = 0
        
    def add_step(self, step_description, before_count, after_count):
        """Add a filtering step to the report"""
        self.steps.append({
            'description': step_description,
            'before': before_count,
            'after': after_count
        })
        
    def add_warning(self, warning_message):
        """Add a warning message to the report"""
        self.warnings.append(warning_message)
        
    def add_suggestion(self, suggestion):
        """Add a suggestion to the report"""
        self.suggestions.append(suggestion)
        
    def set_initial_count(self, count):
        """Set the initial count of questions"""
        self.initial_count = count
        
    def set_final_count(self, count):
        """Set the final count of questions"""
        self.final_count = count
        
    def generate_report(self):
        """Generate a comprehensive filtering report"""
        report = "\n" + "="*60 + "\n"
        report += "FILTERING PROCESS REPORT\n"
        report += "="*60 + "\n"
        
        report += f"Initial questions in database: {self.initial_count}\n\n"
        
        if self.steps:
            report += "Step-by-step filtering:\n"
            report += "-" * 30 + "\n"
            for step in self.steps:
                report += f"• {step['description']}: {step['before']} → {step['after']} questions\n"
            
            report += f"\nFinal filtered results: {self.final_count} questions\n"
        
        if self.warnings:
            report += "\nWARNINGS:\n"
            report += "-" * 15 + "\n"
            for warning in self.warnings:
                report += f"⚠️  {warning}\n"
        
        if self.suggestions:
            report += "\nSUGGESTIONS:\n"
            report += "-" * 20 + "\n"
            for suggestion in self.suggestions:
                report += f"💡 {suggestion}\n"
        
        report += "\n" + "="*60 + "\n"
        return report